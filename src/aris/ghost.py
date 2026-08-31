"""Ghost driver — parallel simulation of ARIS's recommended strategy.

Created at the moment ARIS's call diverges from what the real driver did.
Updated every lap using the same simulate() physics as the main engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aris.state import RaceState

PIT_LOSS_S = 22.5
RESOLUTION_THRESHOLD_S = 5.0
# Minimum laps after divergence before we declare an outcome.
# Prevents the one-shot pit-loss from triggering immediate ARIS_INCORRECT.
RESOLUTION_MIN_LAPS = 25


@dataclass
class GhostPlan:
    """ARIS pit schedule from a lights-out ``recommend()`` call."""

    pit_laps: list[int]
    pit_compounds: list[str]
    start_compound: str
    aris_action: str = ""
    decision_lap: int = 1


@dataclass
class GhostState:
    """Parallel simulation of the ARIS-recommended strategy.

    ``ghost_cumulative_delta`` is positive when the ghost (ARIS call) is ahead
    of the real driver: positive means ARIS's strategy is winning.
    """

    driver_code: str

    divergence_lap: int

    aris_action: str
    aris_tyre: str

    real_action: str

    ghost_lap: int = 0
    ghost_tyre: str = ""
    ghost_tyre_age: int = 0
    ghost_position: int = 0
    ghost_cumulative_delta: float = 0.0
    gap_to_leader_s: float = 0.0

    delta_history: list[dict] = field(default_factory=list)

    active: bool = True
    resolved_lap: Optional[int] = None
    outcome: Optional[str] = None
    from_lap_one: bool = False
    typical_lap_s: float = 90.0
    plan_pit_laps: list[int] = field(default_factory=list)
    plan_pit_compounds: list[str] = field(default_factory=list)
    ghost_lap_s: float = 0.0
    real_lap_s: float = 0.0


def _estimate_ghost_position(
    ghost: GhostState,
    race_state: "RaceState",
    rival_estimates: list,
) -> int:
    """Estimate the ghost's current track position.

    Logic:
    1. Start from the real driver's current position.
    2. For each rival, compare the ghost's cumulative_delta to that rival's
       estimated time gap relative to the focus driver.
    3. If ghost is X seconds ahead of real → count how many rivals ahead of
       real are within X seconds (ghost passed them).
    4. If ghost is behind real → count how many rivals behind real have less
       gap than abs(delta) (they passed the ghost).

    Returns an estimated 1-based position (clamped 1–20).
    This is approximate (gap-based, not lap-time-based) but much better than
    the frozen-at-divergence approach.
    """
    real_position = int(race_state.position or ghost.ghost_position or 10)
    delta = ghost.ghost_cumulative_delta

    if not rival_estimates:
        return max(1, min(20, real_position))

    if delta > 0:  # ghost is ahead of real driver
        # Count cars that were ahead of real driver but within delta seconds
        passed = sum(
            1
            for r in rival_estimates
            if (getattr(r, "gap_to_focus", None) or 0) < 0
            and abs(getattr(r, "gap_to_focus", 0)) < delta
        )
        return max(1, real_position - passed)
    else:  # ghost is behind real driver
        # Count cars that were behind real driver but have less gap than abs(delta)
        overtaken = sum(
            1
            for r in rival_estimates
            if (getattr(r, "gap_to_focus", None) or 0) > 0
            and getattr(r, "gap_to_focus", 0) < abs(delta)
        )
        return min(20, real_position + overtaken)


def _call_simulate(simulate_fn: Callable, state: "RaceState", action, times: list[float]):
    """Call simulate(); capture this-lap time via lap_times_out when supported."""
    try:
        return simulate_fn(state, action, lap_times_out=times)
    except TypeError:
        return simulate_fn(state, action)


def _this_lap_s(outcome, times: list[float]) -> float:
    if times:
        return float(times[0])
    return float(getattr(outcome, "mean_lap_time_s", 0.0) or 0.0)


def _effective_pit_loss_s(race_state: "RaceState", override: float | None = None) -> float:
    if override is not None:
        return float(override)
    try:
        from aris.simulate import _pit_loss_s, get_pit_loss

        green = float(_pit_loss_s(race_state))
        return float(
            get_pit_loss(green, race_state.track_status, circuit_key=race_state.country)
        )
    except Exception:
        return PIT_LOSS_S


def advance_ghost_lap(
    ghost: GhostState,
    race_state: "RaceState",
    simulate_fn: Callable,
    rival_estimates: list | None = None,
    *,
    resolve: bool = True,
    ghost_pits: bool = False,
    real_pits: bool = False,
    pit_loss_s: float | None = None,
    pit_compound: str | None = None,
) -> GhostState:
    """Advance the ghost driver by one lap.

    Uses the same simulate() physics as the main recommendation engine.
    Compares this lap's STAY_OUT time (ghost compound/age vs real compound/age)
    to build the cumulative delta — positive means ghost is ahead.

    ``rival_estimates`` is used for dynamic position estimation (T6).
    Parallel (lap-1) ghosts pass ``resolve=False`` so they stay on the map
    for the whole race. Pit laps add circuit pit-loss to the car that stopped.
    """
    from aris.simulate import ActionKind, StrategyAction

    stay_out = StrategyAction(kind=ActionKind.STAY_OUT)

    # Ghost state: same race context but with ARIS-recommended tyre
    ghost_race_state = race_state.model_copy(
        update={
            "compound": ghost.ghost_tyre,
            "tyre_life": max(0, int(ghost.ghost_tyre_age)),
        }
    )

    ghost_times: list[float] = []
    real_times: list[float] = []
    ghost_outcome = _call_simulate(simulate_fn, ghost_race_state, stay_out, ghost_times)
    real_outcome = _call_simulate(simulate_fn, race_state, stay_out, real_times)

    # positive lap_delta → ghost is faster this lap
    ghost_lap_s = _this_lap_s(ghost_outcome, ghost_times)
    real_lap_s = _this_lap_s(real_outcome, real_times)
    loss = _effective_pit_loss_s(race_state, pit_loss_s)
    if ghost_pits:
        ghost_lap_s += loss
    if real_pits:
        real_lap_s += loss
    lap_delta = real_lap_s - ghost_lap_s

    ghost.ghost_lap_s = ghost_lap_s
    ghost.real_lap_s = real_lap_s
    ghost.ghost_cumulative_delta += lap_delta
    if ghost_pits:
        ghost.ghost_tyre = str(pit_compound or ghost.ghost_tyre).upper()
        ghost.ghost_tyre_age = 1
    else:
        ghost.ghost_tyre_age += 1
    ghost.ghost_lap += 1

    # T6: dynamic position estimation based on cumulative delta and rival gaps.
    ghost.ghost_position = _estimate_ghost_position(
        ghost, race_state, rival_estimates or []
    )

    ghost.delta_history.append(
        {
            "lap": race_state.lap_number,
            "delta": round(ghost.ghost_cumulative_delta, 3),
            "ghost_pos": ghost.ghost_position,
            "real_pos": race_state.position or 0,
        }
    )

    if not resolve:
        if race_state.lap_number >= race_state.total_laps:
            if abs(ghost.ghost_cumulative_delta) < 2.0:
                ghost.outcome = "INCONCLUSIVE"
            else:
                ghost.outcome = (
                    "ARIS_CORRECT"
                    if ghost.ghost_cumulative_delta > 0
                    else "ARIS_INCORRECT"
                )
            ghost.resolved_lap = race_state.lap_number
        return ghost

    # Resolution check — only after RESOLUTION_MIN_LAPS laps so the pit-loss
    # one-shot (±22.5 s at divergence) does not trigger an immediate outcome.
    if ghost.ghost_lap >= RESOLUTION_MIN_LAPS and abs(ghost.ghost_cumulative_delta) > RESOLUTION_THRESHOLD_S:
        ghost.active = False
        ghost.resolved_lap = race_state.lap_number
        ghost.outcome = (
            "ARIS_CORRECT"
            if ghost.ghost_cumulative_delta > 0
            else "ARIS_INCORRECT"
        )
    elif race_state.lap_number >= race_state.total_laps:
        ghost.active = False
        ghost.resolved_lap = race_state.lap_number
        if abs(ghost.ghost_cumulative_delta) < 2.0:
            ghost.outcome = "INCONCLUSIVE"
        else:
            ghost.outcome = (
                "ARIS_CORRECT"
                if ghost.ghost_cumulative_delta > 0
                else "ARIS_INCORRECT"
            )

    return ghost


def maybe_create_ghost(
    recommendation: dict,
    real_action: str,
    race_state: "RaceState",
) -> Optional[GhostState]:
    """Return a GhostState if ARIS's recommendation differs from the real driver's action.

    ``recommendation`` is the top Recommendation dict (or Recommendation model).
    ``real_action`` is the action string the real driver actually took.

    'Differs' means the action strings differ OR the compound is different.
    Returns None when ARIS and the driver agree.
    """
    # Normalise recommendation to a dict
    if hasattr(recommendation, "model_dump"):
        rec_dict = recommendation.model_dump()
    elif hasattr(recommendation, "__dict__"):
        rec_dict = recommendation.__dict__
    else:
        rec_dict = dict(recommendation)

    aris_label = str(rec_dict.get("label", ""))
    action_obj = rec_dict.get("action", {})
    if hasattr(action_obj, "model_dump"):
        action_obj = action_obj.model_dump()

    # Extract ARIS action string
    action_kind = str(action_obj.get("kind", "stay_out"))
    pit_compound = str(action_obj.get("pit_compound") or "HARD").upper()

    if action_kind == "stay_out" and not action_obj.get("pit_laps"):
        aris_action = "STAY_OUT"
        aris_tyre = str(race_state.compound).upper()
    elif action_kind == "pit_now":
        aris_action = f"PIT_NOW_{pit_compound}"
        aris_tyre = pit_compound
    elif action_kind == "pit_lap":
        pit_lap = action_obj.get("pit_lap")
        aris_action = f"PIT_L{pit_lap}_{pit_compound}"
        aris_tyre = pit_compound
    else:
        aris_action = aris_label or action_kind.upper()
        aris_tyre = str(race_state.compound).upper()

    real_action_norm = real_action.upper().strip()

    # No divergence
    if aris_action == real_action_norm:
        return None
    # Both stay-out with different labels — treat as same
    if "STAY" in aris_action and "STAY" in real_action_norm:
        return None

    # STAY_OUT ghost: keeps the same tyre, aging from the current life.
    # PIT ghost: starts on fresh rubber (age 0 / 1).
    ghost_initial_tyre_age = (
        int(race_state.tyre_life or 0)
        if ("STAY" in aris_action)
        else 0
    )

    ghost = GhostState(
        driver_code=race_state.driver_code,
        divergence_lap=race_state.lap_number,
        aris_action=aris_action,
        aris_tyre=aris_tyre,
        real_action=real_action_norm,
        ghost_tyre=aris_tyre,
        ghost_tyre_age=ghost_initial_tyre_age,
        ghost_position=race_state.position or 0,
    )

    # If ARIS recommended pit but real driver stayed out:
    # ghost car went into pits → loses pit_loss_s vs real car that stayed on track.
    if "PIT" in aris_action and "STAY" in real_action_norm:
        ghost.ghost_cumulative_delta -= PIT_LOSS_S

    # If ARIS recommended stay-out but real driver pitted:
    # real car paid pit cost → ghost gained pit_loss_s immediately on track.
    elif "STAY" in aris_action and "PIT" in real_action_norm:
        ghost.ghost_cumulative_delta += PIT_LOSS_S

    ghost.delta_history.append(
        {
            "lap": race_state.lap_number,
            "delta": round(ghost.ghost_cumulative_delta, 3),
            "ghost_pos": ghost.ghost_position,
            "real_pos": race_state.position or 0,
        }
    )

    return ghost


def _action_as_dict(action) -> dict:
    if action is None:
        return {}
    if hasattr(action, "model_dump"):
        return action.model_dump()
    if hasattr(action, "__dict__") and not isinstance(action, dict):
        return dict(action.__dict__)
    return dict(action) if action else {}


def _recommendation_as_dict(recommendation) -> dict:
    if recommendation is None:
        return {}
    if hasattr(recommendation, "model_dump"):
        return recommendation.model_dump()
    if hasattr(recommendation, "__dict__") and not isinstance(recommendation, dict):
        return dict(recommendation.__dict__)
    return dict(recommendation)


def _is_line_action(action: dict) -> bool:
    kind = str(action.get("kind") or "").lower()
    return kind in ("lift", "brake")


def pick_strategy_recommendation(rec_result) -> dict | None:
    """First recommend() card that is a race strategy (not lift/brake/reset)."""
    recs = getattr(rec_result, "recommendations", None)
    if recs is None and isinstance(rec_result, list):
        recs = rec_result
    recs = recs or []
    for rec in recs:
        data = _recommendation_as_dict(rec)
        if str(data.get("label") or "") == "STRATEGY_RESET":
            continue
        action = _action_as_dict(data.get("action"))
        if _is_line_action(action):
            continue
        data["action"] = action
        return data
    if recs:
        data = _recommendation_as_dict(recs[0])
        data["action"] = _action_as_dict(data.get("action"))
        return data
    return None


def schedule_from_recommendation(
    recommendation,
    *,
    start_compound: str,
    lap_number: int,
) -> GhostPlan:
    """Convert a recommend() card into a full-race pit schedule."""
    from aris.physics.tires import normalize_compound

    start = normalize_compound(str(start_compound or "MEDIUM"))
    data = _recommendation_as_dict(recommendation)
    action = _action_as_dict(data.get("action"))
    label = str(data.get("label") or "")
    kind = str(action.get("kind") or "stay_out").lower()
    pit_compound = normalize_compound(str(action.get("pit_compound") or "HARD"))

    pit_laps_raw = action.get("pit_laps") or []
    if pit_laps_raw:
        compounds = [
            normalize_compound(c) for c in (action.get("pit_compounds") or [])
        ]
        pits = [int(x) for x in pit_laps_raw]
        while len(compounds) < len(pits):
            compounds.append(pit_compound)
        return GhostPlan(
            pit_laps=pits,
            pit_compounds=compounds,
            start_compound=start,
            aris_action=label or f"Plan: {pits} -> {compounds}",
            decision_lap=int(lap_number),
        )
    if kind == "pit_now":
        return GhostPlan(
            pit_laps=[int(lap_number)],
            pit_compounds=[pit_compound],
            start_compound=start,
            aris_action=label or f"PIT_NOW_{pit_compound}",
            decision_lap=int(lap_number),
        )
    if kind == "pit_lap" and action.get("pit_lap") is not None:
        pit_lap = int(action["pit_lap"])
        return GhostPlan(
            pit_laps=[pit_lap],
            pit_compounds=[pit_compound],
            start_compound=start,
            aris_action=label or f"PIT_L{pit_lap}_{pit_compound}",
            decision_lap=int(lap_number),
        )
    return GhostPlan(
        pit_laps=[],
        pit_compounds=[],
        start_compound=start,
        aris_action=label or "STAY_OUT",
        decision_lap=int(lap_number),
    )


def create_ghost_from_plan(
    race_state: "RaceState",
    plan: GhostPlan,
    *,
    typical_lap_s: float = 90.0,
    real_action: str = "GRID",
) -> GhostState:
    """Always-on ghost from lap 1 following ``plan`` (not divergence-gated)."""
    from aris.physics.tires import normalize_compound

    start = normalize_compound(plan.start_compound or race_state.compound)
    _log.debug(
        "create_ghost_from_plan driver=%s seed_position=%s pit_laps=%s",
        race_state.driver_code,
        race_state.position,
        list(plan.pit_laps),
    )
    return GhostState(
        driver_code=race_state.driver_code,
        divergence_lap=1,
        aris_action=plan.aris_action or "ARIS",
        aris_tyre=start,
        real_action=real_action,
        ghost_tyre=start,
        ghost_tyre_age=int(race_state.tyre_life or 1) or 1,
        ghost_position=int(race_state.position or 1),
        from_lap_one=True,
        typical_lap_s=float(typical_lap_s or 90.0),
        plan_pit_laps=list(plan.pit_laps),
        plan_pit_compounds=list(plan.pit_compounds),
        active=True,
    )


def _rank_ghost_in_field(
    ghost_cum: float,
    field_cum: dict[str, float] | None,
    fallback_pos: int,
) -> tuple[int, float]:
    """Rank ghost by ARIS simulated cumulative time vs real field cumulative times.

    Position = 1 + how many real drivers have a lower cumulative time.
    Gap is ghost_cum - leader_cum (leader = fastest real car, or the ghost if ahead).
    """
    if not field_cum:
        return max(1, min(20, fallback_pos)), 0.0
    scores = [(float(t), str(c).upper()) for c, t in field_cum.items()]
    scores.append((float(ghost_cum), "__GHOST__"))
    scores.sort(key=lambda kv: kv[0])
    leader = scores[0][0]
    rank = next((j + 1 for j, (_t, c) in enumerate(scores) if c == "__GHOST__"), fallback_pos)
    gap = max(0.0, float(ghost_cum) - leader)
    return int(rank), float(gap)


def field_cumulative_by_lap(
    lap_times: dict[str, dict[int, float]],
) -> dict[int, dict[str, float]]:
    """driver → {lap: lap_time_s} → {lap: {driver: cumulative_s}}."""
    out: dict[int, dict[str, float]] = {}
    running: dict[str, float] = {}
    all_laps: set[int] = set()
    for times in lap_times.values():
        all_laps.update(int(k) for k in times)
    for lap in sorted(all_laps):
        for code, times in lap_times.items():
            t = times.get(lap)
            if t is None:
                continue
            running[str(code).upper()] = running.get(str(code).upper(), 0.0) + float(t)
        out[int(lap)] = dict(running)
    return out


def r2_ghost_tick(
    lap: int,
    tick: dict,
    pit_laps: list[int],
    *,
    confidence: float = 1.0,
) -> dict:
    """Serialize a score_parallel_ghost tick into the R2 ghost_{DRIVER}.json shape."""
    pits = {int(p) for p in pit_laps}
    pits_done = sum(1 for p in pits if p <= int(lap))
    return {
        "lap": int(lap),
        "position": int(tick.get("ghost_position") or 0),
        "gap_to_leader_s": round(float(tick.get("gap_to_leader_s") or 0.0), 3),
        "compound": str(tick.get("ghost_compound") or tick.get("ghost_tyre") or "HARD"),
        "tyre_life": int(tick.get("ghost_tyre_age") or 0),
        "stint": pits_done + 1,
        "cumulative_delta_s": round(float(tick.get("ghost_cumulative_delta") or 0.0), 3),
        "aris_action": "PIT" if int(lap) in pits else "STAY_OUT",
        "aris_confidence": max(0.0, min(1.0, float(confidence))),
    }


def plan_from_pits(
    pit_laps: list[int],
    pit_compounds: list[str],
    start_compound: str,
    *,
    label: str = "",
) -> GhostPlan:
    from aris.physics.tires import normalize_compound

    pits = [int(x) for x in pit_laps]
    compounds = [normalize_compound(c) for c in pit_compounds]
    while len(compounds) < len(pits):
        compounds.append(normalize_compound(pit_compounds[-1] if pit_compounds else "HARD"))
    return GhostPlan(
        pit_laps=pits,
        pit_compounds=compounds[: len(pits)],
        start_compound=normalize_compound(start_compound),
        aris_action=label or ("STAY_OUT" if not pits else f"PIT_L{pits[0]}_{compounds[0]}"),
        decision_lap=1,
    )


def score_parallel_ghost(
    *,
    template_state: "RaceState",
    lap_rows: list[dict],
    plan: GhostPlan,
    simulate_fn: Callable | None = None,
    typical_lap_s: float = 90.0,
    field_cum_by_lap: dict[int, dict[str, float]] | None = None,
) -> dict[int, dict | None]:
    """Score ARIS vs real from lap 1 using simulate(STAY_OUT) each lap.

    ``lap_rows`` items: lap_number, compound, tyre_life, real_action, position,
    optional fuel_kg / track_status / gap_to_leader_s / lag1_pace / lag2_pace /
    stint_roll3 / rivals.
    """
    from aris.models.features import estimate_fuel_kg
    from aris.physics.tires import normalize_compound
    from aris.simulate import simulate as default_simulate

    sim = simulate_fn or default_simulate
    rows = sorted(
        (r for r in lap_rows if int(r.get("lap_number") or 0) > 0),
        key=lambda r: int(r["lap_number"]),
    )
    if not rows:
        return {}

    first = rows[0]
    start_state = template_state.model_copy(
        update={
            "lap_number": int(first["lap_number"]),
            "compound": normalize_compound(plan.start_compound),
            "tyre_life": 1,
            "position": int(first.get("position") or template_state.position or 1),
        }
    )
    typical = float(typical_lap_s or 90.0)
    if typical <= 1.0:
        typical = 90.0
    ghost = create_ghost_from_plan(start_state, plan, typical_lap_s=typical)
    pit_map = {
        int(lap): normalize_compound(cmp)
        for lap, cmp in zip(plan.pit_laps, plan.pit_compounds, strict=False)
    }
    result: dict[int, dict | None] = {}
    ghost_cum = 0.0
    real_cum_actual = 0.0
    focus_code = str(template_state.driver_code or "").upper()
    total_laps = int(template_state.total_laps or len(rows))

    for row in rows:
        lap_number = int(row["lap_number"])
        real_action = str(row.get("real_action") or "STAY_OUT")
        real_pits = "PIT" in real_action.upper()
        ghost_pits = lap_number in pit_map
        fuel = row.get("fuel_kg")
        if fuel is None:
            fuel = estimate_fuel_kg(lap_number, total_laps=total_laps)
        advance_state = template_state.model_copy(
            update={
                "lap_number": lap_number,
                "compound": normalize_compound(str(row.get("compound") or "HARD")),
                "tyre_life": int(row.get("tyre_life") or 1),
                "fuel_kg": float(fuel),
                "laps_remaining": max(0, total_laps - lap_number),
                "total_laps": total_laps,
                "position": int(row.get("position") or template_state.position or 10),
                "gap_to_leader_s": row.get("gap_to_leader_s", template_state.gap_to_leader_s),
                "gap_ahead_s": row.get("gap_ahead_s", template_state.gap_ahead_s),
                "track_status": str(row.get("track_status") or template_state.track_status or "1"),
                "lag1_pace": row.get("lag1_pace", template_state.lag1_pace),
                "lag2_pace": row.get("lag2_pace", template_state.lag2_pace),
                "stint_roll3": row.get("stint_roll3", template_state.stint_roll3),
            }
        )
        try:
            ghost.real_action = real_action
            ghost = advance_ghost_lap(
                ghost,
                advance_state,
                sim,
                row.get("rivals") or [],
                resolve=False,
                ghost_pits=ghost_pits,
                real_pits=real_pits,
                pit_compound=pit_map.get(lap_number),
            )
        except Exception:
            result[lap_number] = ghost_to_dict(ghost)
            continue
        ghost_cum += float(ghost.ghost_lap_s or 0.0)
        # Actual telemetry lap time when the caller supplied it, else fall back
        # to the model's own STAY_OUT prediction for the real side.
        lap_time_actual = row.get("lap_time_s")
        real_cum_actual += (
            float(lap_time_actual) if lap_time_actual else float(ghost.real_lap_s or 0.0)
        )
        field_now = (field_cum_by_lap or {}).get(lap_number)
        if field_now:
            fallback = int(advance_state.position or ghost.ghost_position or 1)
            # Timing-tower rank must compare like-for-like time bases. `ghost_cum`
            # is a raw model-predicted absolute time (cold-start on lap 1 with no
            # lag context, it can be wildly mis-scaled vs measured lap times —
            # see ISSUES.md Bug 1). Anchor the ghost's absolute cumulative time to
            # the focus driver's *actual measured* cumulative time (from
            # field_cum_by_lap, built off real telemetry) offset by the model's
            # cumulative *delta* — the model is far more reliable at predicting
            # a relative delta between two compounds/strategies sharing the same
            # lag context than it is at predicting an absolute lap time cold.
            # anchor - delta = anchor - (real_lap_s - ghost_lap_s) sum
            #                = anchor - real_cum_modeled + ghost_cum_modeled
            # i.e. this reproduces ghost_cum but rebased onto real measured time.
            anchor = float(field_now.get(focus_code, real_cum_actual))
            ghost_cum_anchored = anchor - float(ghost.ghost_cumulative_delta)
            pos, gap = _rank_ghost_in_field(ghost_cum_anchored, field_now, fallback)
            ghost.ghost_position = pos
            ghost.gap_to_leader_s = gap
            if ghost.delta_history:
                ghost.delta_history[-1]["ghost_pos"] = ghost.ghost_position
                ghost.delta_history[-1]["gap_to_leader_s"] = round(gap, 3)
        if lap_number <= 2:
            _log.debug(
                "ghost lap=%s real_pos=%s ghost_pos=%s delta=%.3f",
                lap_number,
                advance_state.position,
                ghost.ghost_position,
                float(ghost.ghost_cumulative_delta),
            )
        result[lap_number] = ghost_to_dict(ghost)
    return result


def ghost_to_dict(ghost: GhostState) -> dict:
    """Serialise a GhostState for inclusion in the WebSocket/SSE tick payload."""
    typical = float(ghost.typical_lap_s or 90.0) or 90.0
    delta = float(ghost.ghost_cumulative_delta)
    return {
        "driver_code": ghost.driver_code,
        "divergence_lap": ghost.divergence_lap,
        "aris_action": ghost.aris_action,
        "real_action": ghost.real_action,
        "ghost_tyre": ghost.ghost_tyre,
        "ghost_compound": ghost.ghost_tyre,
        "ghost_tyre_age": ghost.ghost_tyre_age,
        "ghost_position": ghost.ghost_position,
        "ghost_lap": ghost.ghost_lap,
        "ghost_cumulative_delta": round(delta, 3),
        "gap_to_leader_s": round(float(ghost.gap_to_leader_s or 0.0), 3),
        "ghost_lap_s": round(float(ghost.ghost_lap_s or 0.0), 3),
        "typical_lap_s": round(typical, 3),
        "from_lap_one": bool(ghost.from_lap_one),
        "plan_pit_laps": list(ghost.plan_pit_laps),
        "plan_pit_compounds": list(ghost.plan_pit_compounds),
        "path_offset": delta / typical,
        "active": ghost.active,
        "outcome": ghost.outcome,
        "delta_history": ghost.delta_history,
    }
