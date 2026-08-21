"""Strategy recommender — enumerate pit / line actions, score with simulate + MC."""

from __future__ import annotations

import os

from pydantic import BaseModel

from aris.montecarlo import DEFAULT_DRAWS, run_mc
from aris.physics.tires import normalize_compound
from aris.physics.traffic import compute_dirty_air_penalty
from aris.physics.wet import (
    WET_RAIN_THRESHOLD_MM,
    effective_rainfall_mm,
    should_recommend_inter,
    should_recommend_wet,
    should_stay_on_wet,
    wet_candidate_delta,
    wet_stay_delta,
)
from aris.simulate import (
    ActionKind,
    StrategyAction,
    extrapolation_std_s,
    extrapolation_weight,
    simulate,
    simulate_overcut_window,
    simulate_undercut,
)
from aris.state import RaceState

PIT_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
UNDERCUT_WINDOW_S = 22.0
FIELD_UNDERCUT_ENV = "ARIS_FIELD_UNDERCUT"
FIELD_OVERCUT_ENV = "ARIS_FIELD_OVERCUT"
FIELD_UNDERCUT_CAP = -1.2
T2D_FALLBACK_NOTE = "undercut fallback: T2-D (no rival estimate)"
OVERCUT_DEPTHS = (2, 4, 6)


class Recommendation(BaseModel):
    rank: int
    label: str
    action: StrategyAction
    delta_vs_stay_out_s: float
    mean_race_time_s: float
    confidence_std_s: float
    p10_delta_s: float
    p90_delta_s: float
    evidence: str
    narration_context: dict
    tactical: str | None = None
    extrapolation_beyond_laps: int = 0
    extrapolation_weight: float = 1.0
    wet_heuristic: bool = False


class RecommendationResult(BaseModel):
    state_lap: int
    driver_code: str
    compound: str
    recommendations: list[Recommendation]


def compute_undercut_bonus(state: RaceState) -> float:
    """Dynamic undercut bonus. Negative = faster (encourages pit). Cap -0.8s."""
    gap_ahead = state.gap_ahead_s
    if gap_ahead is None or not (0 < gap_ahead < UNDERCUT_WINDOW_S):
        return 0.0
    bonus = -0.3
    if gap_ahead < 3.0:
        bonus -= 0.3
    hist = list(state.gap_ahead_history or [])
    if len(hist) >= 3:
        recent = hist[-3:]
        closing_rate = (recent[0] - recent[-1]) / 3.0
        if closing_rate > 0.05:
            bonus -= 0.2
        elif closing_rate < -0.05:
            bonus += 0.1
    return max(bonus, -0.8)


def field_undercut_enabled(raw: str | bool | None = None) -> bool:
    """True only for explicit opt-in. Unset / 0 / false keeps T2-D."""
    if raw is True:
        return True
    if raw is False:
        return False
    if raw is None:
        raw = os.getenv(FIELD_UNDERCUT_ENV, "")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def field_overcut_enabled(raw: str | bool | None = None) -> bool:
    """Default off. Set ARIS_FIELD_OVERCUT=1 to enable; keep off if match-rate < 0.345."""
    if raw is True:
        return True
    if raw is False:
        return False
    if raw is None:
        raw = os.getenv(FIELD_OVERCUT_ENV, "")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def generate_overcut_candidates(
    state: RaceState,
    rival_estimates: list,
    slopes: dict[str, float] | None,
    circuit_pit_loss: float,
) -> list[StrategyAction]:
    """At most 2 OVERCUT_{code}_{N}L actions vs the soonest eligible rival."""
    if state.laps_remaining < 15:
        return []
    if state.gap_ahead_s is not None and state.gap_ahead_s < 2.0:
        return []
    soon = [
        e
        for e in rival_estimates
        if int(e.laps_until_pit) <= 8
        and str(e.confidence) != "LOW"
        and int(e.estimated_pit_lap) > int(state.lap_number)
    ]
    if not soon:
        return []
    soon.sort(key=lambda e: (e.estimated_pit_lap, e.driver_code))
    rival = soon[0]
    pit_compound = state.pit_compound or "HARD"
    ranked: list[tuple[float, int, int]] = []
    for n in OVERCUT_DEPTHS:
        pit_lap = int(rival.estimated_pit_lap) + int(n)
        if pit_lap > state.total_laps:
            continue
        window = simulate_overcut_window(
            state,
            rival,
            extra_laps=n,
            pit_compound=pit_compound,
            circuit_pit_loss=circuit_pit_loss,
            slopes=slopes,
        )
        if window < 0:
            ranked.append((window, n, pit_lap))
    ranked.sort(key=lambda t: t[0])
    out: list[StrategyAction] = []
    for window, n, pit_lap in ranked[:2]:
        out.append(
            StrategyAction(
                kind=ActionKind.PIT_LAP,
                pit_lap=pit_lap,
                pit_compound=pit_compound,
                label_override=f"OVERCUT_{rival.driver_code}_{n}L",
                overcut_rival=rival.driver_code,
                overcut_n=n,
                overcut_window_delta_s=window,
            )
        )
    return out


def compute_field_undercut_value(
    state: RaceState,
    rival_estimates: list,
    pit_compound: str,
    circuit_pit_loss: float,
    slopes: dict[str, float] | None,
    *,
    car_ahead_code: str | None,
) -> tuple[float, str]:
    """Field-aware undercut vs the car ahead. Falls back to T2-D explicitly."""
    if not car_ahead_code or not rival_estimates:
        return compute_undercut_bonus(state), "t2d_missing"
    ahead = next(
        (e for e in rival_estimates if str(e.driver_code).upper() == car_ahead_code.upper()),
        None,
    )
    if ahead is None:
        return compute_undercut_bonus(state), "t2d_missing"
    if int(ahead.estimated_pit_lap) <= int(state.lap_number) + 3:
        return compute_undercut_bonus(state), "t2d"
    delta = simulate_undercut(
        state, ahead, pit_compound, circuit_pit_loss, slopes or {}
    )
    if delta < 0:
        return max(delta, FIELD_UNDERCUT_CAP), "field"
    return compute_undercut_bonus(state), "t2d"


def _undercut_bonus(state: RaceState, action: StrategyAction) -> float:
    if action.kind == ActionKind.STAY_OUT and not action.pit_laps:
        return 0.0
    if action.kind in (ActionKind.LIFT, ActionKind.BRAKE):
        return 0.0
    return compute_undercut_bonus(state)


def _candidate_actions(state: RaceState) -> list[StrategyAction]:
    actions: list[StrategyAction] = [
        StrategyAction(kind=ActionKind.STAY_OUT),
        StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=state.pit_compound),
    ]
    for offset in (1, 2, 3, 5, 8):
        pit_lap = state.lap_number + offset
        if pit_lap > state.total_laps:
            continue
        for compound in PIT_COMPOUNDS:
            if compound == "SOFT" and state.laps_remaining < 15:
                continue
            actions.append(
                StrategyAction(
                    kind=ActionKind.PIT_LAP,
                    pit_lap=pit_lap,
                    pit_compound=compound,
                )
            )

    mid = state.total_laps // 2
    for pits, compounds in (
        ([mid, state.total_laps - 8], ["MEDIUM", "HARD"]),
        ([mid - 5, mid + 10], ["SOFT", "HARD"]),
    ):
        valid = all(1 <= p <= state.total_laps for p in pits)
        if valid and pits[0] >= state.lap_number:
            actions.append(
                StrategyAction(
                    kind=ActionKind.STAY_OUT,
                    pit_laps=pits,
                    pit_compounds=compounds,
                )
            )

    # Physics-backed line actions (replaces former hardcoded DRS/defend deltas).
    for corner in (1, 7, 10):
        actions.append(
            StrategyAction(kind=ActionKind.LIFT, corner_index=corner, distance_m=30.0)
        )
        actions.append(
            StrategyAction(kind=ActionKind.BRAKE, corner_index=corner, distance_m=20.0)
        )
    return actions


HOLD_WET_NARRATION = "Hold tyres — conditions still wet."
WET_HEURISTIC_EVIDENCE = "wet heuristic (uncalibrated — reduced confidence)"
WET_HOLD_LAPS = (3, 5, 8)


def _laps_remaining(state: RaceState) -> int:
    remaining = int(state.laps_remaining or 0)
    if state.total_laps:
        remaining = max(remaining, int(state.total_laps) - int(state.lap_number))
    return remaining


def _wet_stay_card(
    state: RaceState,
    action: StrategyAction,
    delta: float,
    evidence: str,
    *,
    wet_heuristic: bool = True,
) -> Recommendation:
    return Recommendation(
        rank=0,
        label=_label_for(action),
        action=action,
        delta_vs_stay_out_s=delta,
        mean_race_time_s=0.0,
        confidence_std_s=0.0,
        p10_delta_s=delta,
        p90_delta_s=delta,
        evidence=evidence,
        narration_context={
            "driver": state.driver_code,
            "lap": state.lap_number,
            "compound": state.compound,
            "tyre_life": state.tyre_life,
            "laps_remaining": state.laps_remaining,
            "position": state.position,
            "gap_ahead_s": state.gap_ahead_s,
            "strategy": _label_for(action),
            "delta_s": round(delta, 2),
            "wet_heuristic": wet_heuristic,
        },
        wet_heuristic=wet_heuristic,
    )


def _make_stay_out_card(state: RaceState) -> Recommendation:
    return _wet_stay_card(
        state,
        StrategyAction(kind=ActionKind.STAY_OUT),
        0.0,
        "stay on current wet compound",
        wet_heuristic=True,
    )


def _generate_wet_stay_candidates(
    state: RaceState,
    slopes: dict[str, float] | None,
    circuit_pit_loss: float,
) -> list[Recommendation]:
    """Candidates when on a wet compound in rain. No SOFT/MEDIUM/HARD pits."""
    del slopes  # wet stay is a heuristic, not G1.5 dry slopes
    remaining = max(_laps_remaining(state), 1)
    compound = normalize_compound(state.compound)
    cards: list[Recommendation] = [_make_stay_out_card(state)]

    for n in WET_HOLD_LAPS:
        if int(state.lap_number) + int(n) > int(state.total_laps):
            continue
        cards.append(
            _wet_stay_card(
                state,
                StrategyAction(
                    kind=ActionKind.STAY_OUT,
                    label_override=HOLD_WET_NARRATION
                    if n == WET_HOLD_LAPS[0]
                    else f"Hold {n} laps — conditions still wet.",
                ),
                0.0,
                HOLD_WET_NARRATION,
            )
        )

    mm = effective_rainfall_mm(state)
    # INTER→WET only for standing water. Boolean rain (1.2 mm proxy) is not that.
    # WET→INTER (drying) is out of scope until a forecast exists.
    if compound in {"INTERMEDIATE", "INTER"} and mm >= WET_RAIN_THRESHOLD_MM:
        delta = wet_candidate_delta(
            mm, remaining, "WET", pit_loss_s=float(circuit_pit_loss)
        )
        cards.append(
            _wet_stay_card(
                state,
                StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="WET"),
                delta,
                WET_HEURISTIC_EVIDENCE,
            )
        )

    if remaining <= 10:
        delta = -wet_stay_delta(state, remaining)
        cards.append(
            _wet_stay_card(
                state,
                StrategyAction(
                    kind=ActionKind.PIT_NOW,
                    pit_compound=state.pit_compound or "HARD",
                    label_override="DRY_WINDOW — pit for slick (track may be drying)",
                ),
                delta,
                f"{WET_HEURISTIC_EVIDENCE} | DRY_WINDOW",
            )
        )
    return cards


def _is_pure_stay(rec: Recommendation) -> bool:
    action = rec.action
    if action.kind != ActionKind.STAY_OUT or action.pit_laps:
        return False
    return not action.label_override


def _rank_and_trim(
    scored: list[Recommendation],
    state: RaceState,
    *,
    top_k: int,
) -> RecommendationResult:
    scored.sort(key=lambda r: r.delta_vs_stay_out_s)
    stay = next((r for r in scored if _is_pure_stay(r)), None)
    top = scored[:top_k]
    if stay is not None and stay not in top:
        top = top[: max(0, top_k - 1)] + [stay]
    for i, rec in enumerate(top, start=1):
        rec.rank = i
    return RecommendationResult(
        state_lap=state.lap_number,
        driver_code=state.driver_code,
        compound=state.compound,
        recommendations=top,
    )


def _label_for(action: StrategyAction) -> str:
    if action.label_override:
        return action.label_override
    if action.kind == ActionKind.LIFT and action.corner_index and action.distance_m:
        return f"Lift {action.distance_m:.0f}m into T{action.corner_index}"
    if action.kind == ActionKind.BRAKE and action.corner_index and action.distance_m:
        return f"Brake {action.distance_m:.0f}m earlier into T{action.corner_index}"
    if action.pit_laps and action.pit_compounds:
        stops = ", ".join(
            f"L{p}->{c}" for p, c in zip(action.pit_laps, action.pit_compounds, strict=False)
        )
        return f"Plan: {stops}"
    if action.kind == ActionKind.STAY_OUT:
        return "Stay out on current tyres"
    if action.kind == ActionKind.PIT_NOW:
        return f"Pit now for {action.pit_compound}"
    return f"Pit lap {action.pit_lap} for {action.pit_compound}"


def recommend(
    state: RaceState,
    *,
    top_k: int = 3,
    mc_draws: int = DEFAULT_DRAWS,
    include_tactical: bool = True,
    field=None,
) -> RecommendationResult:
    # include_tactical retained for API compatibility; hardcoded DRS/defend
    # deltas were removed in Phase C — line actions are scored via simulate().
    _ = include_tactical
    scored: list[Recommendation] = []

    estimates: list = []
    car_ahead_code: str | None = None
    want_field = field is not None and (
        field_undercut_enabled() or field_overcut_enabled()
    )
    if want_field:
        from aris.field.rivals import estimate_all_rivals

        estimates = estimate_all_rivals(
            field,
            state.driver_code,
            state.lap_number,
            state.total_laps,
            state.country,
        )
        if state.position and int(state.position) > 1:
            ahead_row = next(
                (r for r in field.standings if r.position == int(state.position) - 1),
                None,
            )
            if ahead_row is not None:
                car_ahead_code = str(ahead_row.code)

    from aris.tracks import load_track_config

    track = load_track_config(state.country, year=state.year, round_no=state.round_no)
    slopes = track.compound_slopes
    circuit_pit_loss = float(track.pit_loss_s)
    pit_compound = state.pit_compound or "HARD"

    field_bonus = 0.0
    undercut_source = "t2d"
    t2d = compute_undercut_bonus(state)
    if field_undercut_enabled() and field is not None:
        field_bonus, undercut_source = compute_field_undercut_value(
            state,
            estimates,
            pit_compound,
            circuit_pit_loss,
            slopes,
            car_ahead_code=car_ahead_code,
        )
    else:
        field_bonus = t2d
        undercut_source = "t2d"

    # Rain-lock: on a wet compound in rain, suppress the dry shortlist.
    if should_stay_on_wet(state):
        candidates = _generate_wet_stay_candidates(
            state, slopes or {}, circuit_pit_loss
        )
        if not any(_is_pure_stay(c) for c in candidates):
            candidates.append(_make_stay_out_card(state))
        return _rank_and_trim(candidates, state, top_k=top_k)

    actions = list(_candidate_actions(state))
    if field is not None and field_overcut_enabled() and estimates:
        actions.extend(
            generate_overcut_candidates(
                state, estimates, slopes, circuit_pit_loss
            )
        )

    dirty_air = 0.0
    if field_undercut_enabled():
        dirty_air = compute_dirty_air_penalty(list(state.gap_ahead_history or []))

    for action in actions:
        outcome = simulate(state, action, dirty_air_penalty=dirty_air)
        baseline = outcome.total_race_time_s - outcome.delta_vs_stay_out_s
        if action.kind == ActionKind.STAY_OUT and not action.pit_laps:
            bonus = 0.0
        elif action.kind in (ActionKind.LIFT, ActionKind.BRAKE):
            bonus = 0.0
        elif action.label_override and str(action.label_override).startswith("OVERCUT_"):
            bonus = 0.0
        else:
            bonus = field_bonus
        beyond = outcome.extrapolation_beyond_laps
        weight = extrapolation_weight(beyond)
        extra_std = extrapolation_std_s(beyond)
        # mc_draws<=0: rank on deterministic simulate() only. Live default is
        # still DEFAULT_DRAWS (100). Backtest uses 0 because ranking identity
        # (pit vs stay, lap, compound) is what we score, not MC bands.
        raw_delta = outcome.delta_vs_stay_out_s
        if mc_draws and mc_draws > 0:
            mc = run_mc(
                state, action, n_draws=mc_draws, dirty_air_penalty=dirty_air
            )
            raw_delta = mc.mean_delta_vs_stay_out_s
            mean_time = mc.mean_time_s
            std_time = float(mc.std_time_s) + extra_std
            p10_delta = mc.p10_time_s - baseline
            p90_delta = mc.p90_time_s - baseline
        else:
            mean_time = outcome.total_race_time_s
            std_time = extra_std
            p10_delta = raw_delta * weight
            p90_delta = raw_delta * weight
        # Discount ranking delta when the action's sim runs past observed
        # stint lengths for that compound (G1.1 compounding / G1.2 SOFT n=23
        # at tyre_life>=25). Stay-out delta is 0 so the weight is a no-op.
        delta = raw_delta * weight + bonus
        caveats = [
            c
            for c in (state.confidence_caveat, outcome.extrapolation_caveat)
            if c
        ]
        combined_caveat = "; ".join(caveats) if caveats else None
        evidence = outcome.evidence
        if state.confidence_caveat and state.confidence_caveat not in evidence:
            evidence = f"{evidence} | caveat: {state.confidence_caveat}"
        if bonus < 0 and undercut_source in {"t2d", "t2d_missing"} and state.gap_ahead_s is not None:
            note = f"Gap {state.gap_ahead_s:.1f}s — undercut bonus active."
            if note not in evidence:
                evidence = f"{evidence} | {note}"
        if undercut_source == "t2d_missing" and action.kind not in (
            ActionKind.STAY_OUT,
            ActionKind.LIFT,
            ActionKind.BRAKE,
        ) and not (action.label_override and str(action.label_override).startswith("OVERCUT_")):
            if T2D_FALLBACK_NOTE not in evidence:
                evidence = f"{evidence} | {T2D_FALLBACK_NOTE}"
        if undercut_source == "field" and bonus < 0:
            note = f"Field undercut vs {car_ahead_code}: {bonus:.2f}s."
            if note not in evidence:
                evidence = f"{evidence} | {note}"
        scored.append(
            Recommendation(
                rank=0,
                label=_label_for(action),
                action=action,
                delta_vs_stay_out_s=delta,
                mean_race_time_s=mean_time,
                confidence_std_s=std_time,
                p10_delta_s=p10_delta,
                p90_delta_s=p90_delta,
                evidence=evidence,
                narration_context={
                    "driver": state.driver_code,
                    "lap": state.lap_number,
                    "compound": state.compound,
                    "tyre_life": state.tyre_life,
                    "laps_remaining": state.laps_remaining,
                    "position": state.position,
                    "gap_ahead_s": state.gap_ahead_s,
                    "undercut_bonus_s": round(bonus, 3),
                    "undercut_source": undercut_source if bonus else "none",
                    "overcut_rival": action.overcut_rival,
                    "overcut_n": action.overcut_n,
                    "overcut_window_delta_s": action.overcut_window_delta_s,
                    "strategy": _label_for(action),
                    "delta_s": round(delta, 2),
                    "raw_delta_s": round(raw_delta, 2),
                    "confidence_std_s": round(std_time, 2),
                    "confidence_caveat": combined_caveat,
                    "recent_sc_pace": state.recent_sc_pace,
                    "extrapolation_beyond_laps": beyond,
                    "extrapolation_weight": round(weight, 3),
                    "extrapolation_compound": outcome.extrapolation_compound,
                    "extrapolation_caveat": outcome.extrapolation_caveat,
                },
                tactical=(
                    action.kind.value
                    if action.kind in (ActionKind.LIFT, ActionKind.BRAKE)
                    else None
                ),
                extrapolation_beyond_laps=beyond,
                extrapolation_weight=weight,
            )
        )

    wet_on = should_recommend_inter(state, state.track_status)
    if wet_on:
        mm = effective_rainfall_mm(state)
        remaining = max(int(state.laps_remaining), 1)
        wet_compounds = ["INTERMEDIATE"]
        if should_recommend_wet(state):
            wet_compounds.append("WET")
        for compound in wet_compounds:
            action = StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=compound)
            delta = wet_candidate_delta(
                mm, remaining, compound, pit_loss_s=circuit_pit_loss
            )
            scored.append(
                Recommendation(
                    rank=0,
                    label=_label_for(action),
                    action=action,
                    delta_vs_stay_out_s=delta,
                    mean_race_time_s=0.0,
                    confidence_std_s=0.0,
                    p10_delta_s=delta,
                    p90_delta_s=delta,
                    evidence="wet heuristic (uncalibrated — reduced confidence)",
                    narration_context={
                        "driver": state.driver_code,
                        "lap": state.lap_number,
                        "compound": state.compound,
                        "tyre_life": state.tyre_life,
                        "laps_remaining": state.laps_remaining,
                        "position": state.position,
                        "gap_ahead_s": state.gap_ahead_s,
                        "strategy": _label_for(action),
                        "delta_s": round(delta, 2),
                        "wet_heuristic": True,
                    },
                    wet_heuristic=True,
                )
            )

    scored.sort(key=lambda r: r.delta_vs_stay_out_s)
    if wet_on:
        wet_recs = [r for r in scored if r.wet_heuristic]
        if wet_recs:
            best_wet = min(wet_recs, key=lambda r: r.delta_vs_stay_out_s)
            scored = [best_wet] + [r for r in scored if r is not best_wet]

    # Always surface stay-out so the engineer can reject a pit push — even when
    # every pit option scores better on raw delta.
    stay = next(
        (r for r in scored if r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps),
        None,
    )
    top = scored[:top_k]
    if stay is not None and stay not in top:
        top = top[: max(0, top_k - 1)] + [stay]

    for i, rec in enumerate(top, start=1):
        rec.rank = i

    return RecommendationResult(
        state_lap=state.lap_number,
        driver_code=state.driver_code,
        compound=state.compound,
        recommendations=top,
    )
