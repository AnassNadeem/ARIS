"""Strategy recommender — enumerate pit / line actions, score with simulate + MC."""

from __future__ import annotations

import logging
import math
import os
import time
from collections import deque

from pydantic import BaseModel

_log = logging.getLogger(__name__)

# Rolling wall-clock samples for recommend() (ms). Used by latency_stats() /
# scripts/bench_recommend_latency.py — not part of ranking.
_LATENCY_SAMPLES_MS: deque[float] = deque(maxlen=512)

from aris.fsm import get_phase_config
from aris.montecarlo import DEFAULT_DRAWS, run_mc
from aris.physics.tires import get_deg_slope, normalize_compound
from aris.physics.traffic import compute_dirty_air_penalty
from aris.physics.wet import (
    INTER_RAIN_THRESHOLD_MM,
    WET_FORCE_MARGIN_S,
    WET_RAIN_THRESHOLD_MM,
    effective_rainfall_mm,
    should_recommend_inter,
    should_recommend_wet,
    should_stay_on_wet,
    wet_candidate_delta,
    wet_stay_delta,
)
from aris.risk.sc_risk_model import (
    circuit_key,
    default_feature_row,
    load_historical_rates,
    predict_sc_risk,
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
from aris.uncertainty.conformal import (
    conformal_for_stint,
    load_conformal_result,
    prediction_interval,
)

PIT_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
UNDERCUT_WINDOW_S = 22.0
FIELD_UNDERCUT_ENV = "ARIS_FIELD_UNDERCUT"
FIELD_OVERCUT_ENV = "ARIS_FIELD_OVERCUT"
FIELD_UNDERCUT_CAP = -1.2
# Conservative prior: clean-air / no-overtake value of emerging ahead of a
# rival who boxes in N laps. Dirty air is 0.15 s/lap × ~3 laps ≈ 0.45 s;
# 0.8 s is a slightly conservative envelope, not a fitted constant.
TRACK_POSITION_VALUE = 0.8
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
    cql_q_delta: float = 0.0
    rank_score: float = 0.0
    confidence_note: str | None = None


class RecommendationResult(BaseModel):
    state_lap: int
    driver_code: str
    compound: str
    recommendations: list[Recommendation]
    # Wall-clock for this call (physics → simulate → optional MC). Not scored.
    latency_ms: float | None = None


def latency_stats() -> dict[str, float | int]:
    """Aggregate recommend() latencies recorded in this process.

    Returns empty dict when no samples have been recorded yet.
    """
    samples = list(_LATENCY_SAMPLES_MS)
    if not samples:
        return {}
    ordered = sorted(samples)
    n = len(ordered)
    p95_idx = min(n - 1, max(0, int(math.ceil(0.95 * n) - 1)))
    return {
        "n": n,
        "avg_ms": round(sum(ordered) / n, 2),
        "p50_ms": round(ordered[n // 2], 2),
        "p95_ms": round(ordered[p95_idx], 2),
        "min_ms": round(ordered[0], 2),
        "max_ms": round(ordered[-1], 2),
    }


def reset_latency_stats() -> None:
    _LATENCY_SAMPLES_MS.clear()


def sc_risk_narration_line(state: RaceState) -> str | None:
    """Radio addendum when SC/VSC risk is elevated. Does not affect ranking."""
    p = float(getattr(state, "p_sc_next_5_laps", 0.0) or 0.0)
    if p <= 0.20:
        return None
    line = (
        f"SC/VSC risk elevated: {p:.0%} in next 5 laps. "
        f"Consider pitting under neutralisation if the window opens."
    )
    # Check if risk is primarily circuit-driven (high historical rate) vs live signal.
    # Race-level SC rates (Azerbaijan=1.0) are a different scale than p_sc_next_5;
    # compare against the circuit-only model output (no yellows/retirements/density/rain)
    # so the note fires when we are echoing the circuit prior, not a live incident.
    circuit = str(
        getattr(state, "country", None) or getattr(state, "track_name", "") or ""
    )
    historical_rate = load_historical_rates().get(circuit_key(circuit), 0.07)
    prior_p5, _ = predict_sc_risk(
        default_feature_row(
            circuit=circuit,
            lap_number=int(getattr(state, "lap_number", 1) or 1),
            total_laps=int(getattr(state, "total_laps", 0) or 1),
            rain_flag=False,
            track_temp_c=getattr(state, "track_temp_c", None),
        )
    )
    if abs(p - prior_p5) < 0.10 or abs(p - historical_rate) < 0.10:
        line = (
            f"{line} "
            "(Note: SC risk estimate is primarily based on circuit history, "
            "not real-time incident detection.)"
        )
    return line


def _apply_conformal_band(
    rec: Recommendation, state: RaceState
) -> Recommendation:
    """Overlay split-conformal p10/p90 on the point delta. Ranking is unchanged."""
    remaining = int(getattr(state, "laps_remaining", 0) or 0)
    if state.total_laps:
        remaining = max(remaining, int(state.total_laps) - int(state.lap_number))
    payload = conformal_for_stint(load_conformal_result(), remaining)
    if payload is None:
        return rec
    lo, hi = prediction_interval(float(rec.delta_vs_stay_out_s), payload)
    note = (
        f"±{payload['q_hat']:.1f}s (90% conformal band, "
        f"n={payload['n_calibration']})"
    )
    rec.p10_delta_s = float(lo)
    rec.p90_delta_s = float(hi)
    rec.confidence_note = note
    rec.narration_context = {
        **rec.narration_context,
        "p10": float(lo),
        "p90": float(hi),
        "confidence_note": note,
    }
    return rec


def _stamp_uncertainty(
    result: RecommendationResult, state: RaceState
) -> RecommendationResult:
    """Attach conformal bands and SC-risk narration. Does not change rank order."""
    line = sc_risk_narration_line(state)
    p5 = float(getattr(state, "p_sc_next_5_laps", 0.07) or 0.07)
    p10 = float(getattr(state, "p_sc_next_10_laps", 0.12) or 0.12)
    for rec in result.recommendations:
        _apply_conformal_band(rec, state)
        extra = {
            "p_sc_next_5_laps": p5,
            "p_sc_next_10_laps": p10,
        }
        if line:
            extra["sc_risk_line"] = line
        rec.narration_context = {**rec.narration_context, **extra}
    return result


def _mc_enabled() -> bool:
    return os.getenv("ARIS_USE_MC", "").strip() == "1"


def _build_mc_state(state: RaceState, conformal_result: dict | None) -> dict:
    remaining = max(_laps_remaining(state), 1)
    payload = conformal_for_stint(conformal_result, remaining) if conformal_result else None
    payload = payload or conformal_result or {}
    mae = float(payload.get("median_abs_error") or 0.0)
    if mae <= 0.0:
        q_hat = float(payload.get("q_hat") or 0.0)
        mae = q_hat / math.sqrt(remaining) if q_hat else 0.05
    deg_sigma = mae / math.sqrt(remaining)
    p5 = float(getattr(state, "p_sc_next_5_laps", 0.07) or 0.07)
    p5 = min(max(p5, 0.0), 0.999)
    p_sc_per_lap = 1.0 - (1.0 - p5) ** (1.0 / 5.0)
    base = float(state.lag1_pace or state.stint_roll3 or 90.0)
    slope = get_deg_slope(
        state.compound,
        circuit_id=state.country,
        year=int(state.year) if state.year else None,
        round_number=int(state.round_no) if state.round_no else None,
    )
    return {
        "laps_remaining": remaining,
        "base_lap_time": base,
        "deg_slope": slope,
        "deg_sigma": max(deg_sigma, 0.01),
        "tyre_age": int(state.tyre_life or 1),
        "p_sc_per_lap": p_sc_per_lap,
    }


def _rec_to_mc_action(
    rec: Recommendation, state: RaceState, pit_loss_s: float
) -> dict | None:
    action = rec.action
    if action.kind in (ActionKind.LIFT, ActionKind.BRAKE):
        return None
    pit_lap: int | None = None
    compound = normalize_compound(action.pit_compound or state.compound)
    loss = 0.0
    remaining = _laps_remaining(state)
    if action.kind == ActionKind.PIT_NOW:
        pit_lap = 0
        loss = float(pit_loss_s)
    elif action.kind == ActionKind.PIT_LAP and action.pit_lap is not None:
        pit_lap = int(action.pit_lap) - int(state.lap_number)
        if pit_lap < 0:
            pit_lap = 0
        loss = float(pit_loss_s)
    elif action.pit_laps:
        pit_lap = int(action.pit_laps[0]) - int(state.lap_number)
        if pit_lap < 0:
            pit_lap = 0
        if action.pit_compounds:
            compound = normalize_compound(action.pit_compounds[0])
        loss = float(pit_loss_s)
    if pit_lap is not None and pit_lap >= remaining:
        pit_lap = None
        loss = 0.0
    slope = get_deg_slope(
        compound,
        circuit_id=state.country,
        year=int(state.year) if state.year else None,
        round_number=int(state.round_no) if state.round_no else None,
    )
    return {
        "name": rec.label,
        "pit_lap": pit_lap,
        "compound": compound,
        "pit_compound_slope": slope,
        "pit_loss": loss,
    }


def _maybe_rerank_mc(
    shortlist: list[Recommendation], state: RaceState
) -> list[Recommendation]:
    """Re-rank the deterministic top-k with vectorised MC. Opt-in via ARIS_USE_MC=1."""
    if not _mc_enabled() or len(shortlist) < 2:
        return shortlist
    try:
        from aris.physics.tyre_warmup import tyre_warmup_lap1
        from aris.simulate_mc import compare_actions_mc
        from aris.tracks import load_track_config

        track = load_track_config(state.country, year=state.year, round_no=state.round_no)
        pit_loss = float(track.pit_loss_s)
        actions: list[dict] = []
        recs: list[Recommendation] = []
        for rec in shortlist:
            payload = _rec_to_mc_action(rec, state, pit_loss)
            if payload is None:
                continue
            actions.append(payload)
            recs.append(rec)
        if len(actions) < 2:
            return shortlist
        warmups = {
            compound: tyre_warmup_lap1(compound)
            for compound in ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "INTER", "WET")
        }
        mc_results = compare_actions_mc(
            actions=actions,
            base_state=_build_mc_state(state, load_conformal_result()),
            n_scenarios=200,
            warmup_penalties=warmups,
            seed=42,
        )
        by_name = {row["action"]: row for row in mc_results}
        for rec in recs:
            row = by_name.get(rec.label)
            if row is None:
                continue
            rec.mean_race_time_s = float(row["expected_total_s"])
            rec.rank_score = float(row["delta_vs_stay"])
            rec.delta_vs_stay_out_s = float(row["delta_vs_stay"])
            rec.p10_delta_s = float(row["p10_s"]) - float(row["expected_total_s"]) + float(
                row["delta_vs_stay"]
            )
            rec.p90_delta_s = float(row["p90_s"]) - float(row["expected_total_s"]) + float(
                row["delta_vs_stay"]
            )
            rec.narration_context = {
                **rec.narration_context,
                "mc": True,
                "expected_total_s": round(float(row["expected_total_s"]), 2),
                "p_best": round(float(row["p_best"]), 3),
                "mc_p10_s": round(float(row["p10_s"]), 2),
                "mc_p90_s": round(float(row["p90_s"]), 2),
            }
        scored_names = {r.label for r in recs}
        mc_sorted = [r for r in recs]
        mc_sorted.sort(key=lambda r: (r.rank_score, r.delta_vs_stay_out_s))
        leftovers = [r for r in shortlist if r.label not in scored_names]
        return mc_sorted + leftovers
    except Exception:
        _log.debug("vectorised MC re-rank failed — using deterministic shortlist", exc_info=True)
        return shortlist


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
    """Default ON as of T5 (gate cleared: 25/56 = 0.446 with rival-aware scoring).

    Set ARIS_FIELD_UNDERCUT=0 to disable and revert to the T2-D flat-bonus path.
    Pass ``raw=False`` explicitly in tests that want the legacy path.
    """
    if raw is False:
        return False
    if raw is True:
        return True
    if raw is None:
        raw = os.getenv(FIELD_UNDERCUT_ENV, "1")
    env_str = str(raw).strip().lower()
    # Only disable when explicitly set to falsy values
    return env_str not in ("0", "false", "no", "off")


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
    # Suppress overcut when our tyres are already younger than the field median.
    # A car that just pitted and has fresh rubber has no overcut position: we
    # cannot gain by staying out further while rivals pit. Only generate overcut
    # cards when our tyre_life >= field median (i.e., we are the older-tyre car).
    if rival_estimates:
        tyre_lives = [int(e.tyre_life) for e in rival_estimates if (e.tyre_life or 0) > 0]
        if tyre_lives:
            field_median = sorted(tyre_lives)[len(tyre_lives) // 2]
            if int(state.tyre_life) < field_median:
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
        if field_overcut_enabled():
            # T7 rival-aware model: remaining-race comparison beats physics window.
            score = _score_overcut_candidate(
                state,
                rival,
                pit_compound=pit_compound,
                circuit_pit_loss=circuit_pit_loss,
                slopes=slopes,
            )
            # Positive score → overcut works. Negate so lower = better (consistent
            # with the rest of the scoring where negative delta = faster).
            window = -score if score > 0 else 0.0
        else:
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


def _infer_rival_expected_compound(
    rival_code: str,
    current_lap: int,
    session_stints: dict,
) -> str:
    """Infer the compound a rival will likely pit onto.

    Logic (priority order):
    1. If the rival has used SOFT + MEDIUM already → likely HARD next.
    2. If rival hasn't used SOFT and early in the race → might SOFT at end.
    3. If last stint (≤ 15 laps remaining from context) → hardest available.
    4. Default: HARD.

    ``session_stints`` is a dict of driver_code → list of {compound} dicts.
    """
    if not session_stints or rival_code not in session_stints:
        return "HARD"

    stints = session_stints.get(rival_code) or []
    used = {str(s.get("compound", "")).upper() for s in stints if s.get("compound")}

    if "SOFT" in used and "MEDIUM" in used:
        return "HARD"
    if "SOFT" not in used and current_lap < 20:
        return "SOFT"
    if "MEDIUM" not in used:
        return "MEDIUM"
    return "HARD"


def _infer_focus_compound(
    state: "RaceState",
    stints_for_driver: list[dict],
    race_frac: float,
) -> str:
    """Infer the optimal pit compound for ARIS's focus driver.

    When ``stints_for_driver`` is empty (no stint history recorded — test
    fixtures, lap-1 edge cases) the function falls back to
    ``state.pit_compound`` to preserve backward compatibility and the
    Zandvoort identity test.

    Logic (in priority order, applied when stints are available):
    1. SOFT + MEDIUM already used → HARD (FIA two-compound rule fulfilled).
    2. SOFT + HARD already used → MEDIUM.
    3. MEDIUM + HARD already used → SOFT (unusual but logically correct).
    4. Only SOFT used → HARD (SOFT→HARD is the dominant 2nd-stint pattern;
       returning MEDIUM here caused 2024 regressions).
    5. Only MEDIUM used, race_frac > 0.60 → HARD (late race).
    6. Only MEDIUM used, laps_remaining ≤ 25 → HARD (short final stint).
    7. Only MEDIUM used, laps_remaining > 25 → MEDIUM (bridge to 3rd stint).
    8. Only HARD used → MEDIUM.
    9. Default → MEDIUM (safer than HARD for a second stint).
    """
    if not stints_for_driver:
        # No history → preserve whatever state.pit_compound was set to.
        return str(getattr(state, "pit_compound", None) or "HARD")

    used_compounds = {
        str(s.get("compound", "")).upper()
        for s in stints_for_driver
        if s.get("compound")
    }
    laps_remaining = int(
        getattr(state, "laps_remaining", max(0, state.total_laps - state.lap_number))
    )

    if "SOFT" in used_compounds and "MEDIUM" in used_compounds:
        return "HARD"
    if "SOFT" in used_compounds and "HARD" in used_compounds:
        return "MEDIUM"
    if "MEDIUM" in used_compounds and "HARD" in used_compounds:
        return "SOFT"
    if "SOFT" in used_compounds:
        # SOFT-only: HARD is the dominant second-stint compound in 2024 and
        # is usually correct (SOFT→HARD). Returning MEDIUM here broke 2024
        # correct HARD matches. Keep HARD for SOFT-only stints.
        return "HARD"
    if "MEDIUM" in used_compounds:
        if race_frac > 0.60:
            return "HARD"
        return "HARD" if laps_remaining <= 25 else "MEDIUM"
    if "HARD" in used_compounds:
        return "MEDIUM"
    return "MEDIUM"


def _score_overcut_candidate(
    state: RaceState,
    rival,
    pit_compound: str,
    circuit_pit_loss: float,
    slopes: dict[str, float] | None,
    *,
    deg_multiplier: float = 1.0,
) -> float:
    """Score an overcut by computing the gap built vs the rival's pace recovery.

    An overcut is profitable when the gap we build while the rival serves their
    stop and warms up their tyres exceeds the rival's eventual pace advantage on
    fresh rubber.

    Returns seconds of advantage the overcut provides (positive = overcut works,
    i.e. we stay ahead even after the rival's tyre advantage matures).

    This replaces the ``simulate_overcut_window`` physics-delta with a
    remaining-race model consistent with ``_score_undercut_candidate``.
    """
    from aris.physics.tyre_warmup import tyre_warmup_penalty
    from aris.simulate import ActionKind, StrategyAction

    laps_remaining = max(int(state.laps_remaining or 0), 1)
    stay_out = StrategyAction(kind=ActionKind.STAY_OUT)

    N = max(0, int(getattr(rival, "laps_until_pit", 0)))
    rival_compound = str(getattr(rival, "compound", "HARD"))
    rival_tyre_age = int(getattr(rival, "tyre_life", 1) or 1)

    # --- Gap we build while rival is in pits + on warm-up laps ---
    warmup_total = tyre_warmup_penalty(pit_compound)  # lap1 + lap2 penalty
    rival_total_time_away = float(circuit_pit_loss) + warmup_total

    # Our pace loss over the N + 2 lap window (deg still applies).
    # Compare our worn-tyre total time vs a theoretical fresh baseline.
    N_window = N + 2
    our_worn_state = state.model_copy(
        update={"laps_remaining": max(N_window, 1)}
    )
    try:
        our_worn_outcome = simulate(our_worn_state, stay_out, deg_multiplier=deg_multiplier)
        our_worn_time = our_worn_outcome.total_race_time_s
    except Exception:
        return 0.0

    # Theoretical: same window on fresh tyres (deg_multiplier=0 gives pure
    # physics baseline without tyre degradation delta).
    our_fresh_state = state.model_copy(
        update={"tyre_life": 1, "compound": state.compound, "laps_remaining": max(N_window, 1)}
    )
    try:
        our_fresh_outcome = simulate(our_fresh_state, stay_out, deg_multiplier=deg_multiplier)
        our_worn_cost = our_worn_time - our_fresh_outcome.total_race_time_s
    except Exception:
        our_worn_cost = 0.0

    # Gap we build = rival's total time off pace minus our own worn-tyre cost.
    gap_built = rival_total_time_away - our_worn_cost

    # After warm-up, rival is faster by (their fresh slope - our worn slope) per lap.
    from aris.physics.tires import tire_pace_loss
    our_worn_pace_loss = tire_pace_loss(
        state.compound,
        int(state.tyre_life or 1),
        slopes=slopes,
        circuit_id=state.country,
    )
    rival_fresh_pace_loss = tire_pace_loss(
        pit_compound, 3, slopes=slopes, circuit_id=state.country
    )  # post-warm-up
    rival_pace_adv_per_lap = max(0.0, our_worn_pace_loss - rival_fresh_pace_loss)

    # Laps after the rival's warm-up where they can close the gap.
    closing_laps = max(0, laps_remaining - N - 2)

    # Total gap closed by rival after warm-up.
    gap_closed_by_rival = rival_pace_adv_per_lap * closing_laps

    # Net advantage: gap we built minus what rival closes over remaining laps.
    net_advantage = gap_built - gap_closed_by_rival

    return float(net_advantage)


def _score_undercut_candidate(
    state: RaceState,
    rival,
    pit_compound: str,
    circuit_pit_loss: float,
    slopes: dict[str, float] | None,
    *,
    deg_multiplier: float = 1.0,
) -> float:
    """Score an undercut candidate by comparing remaining-race delta.

    Compares: focus car (pits now on ``pit_compound``) vs rival (pits in N
    laps at their estimated pit lap).  Includes warm-up penalty on both
    out-laps and a dirty-air surcharge if we exit the pit lane into traffic.

    Returns seconds gained vs the rival — **positive = undercut works**.

    This is the T5 rival-aware model. It replaces the flat −1.2 s cap from
    the T4 ``simulate_undercut`` path when ``ARIS_FIELD_UNDERCUT=1``.

    T8 Step 1/2 (Cause A regressions) — answers before the implementation:

    1. The ~−0.5 s field bonus after the T8 window bound was **not** a small
       remaining-race delta. ``simulate()`` ignores ``laps_remaining`` and
       loops ``range(lap_number, total_laps+1)``. Focus ran that full window
       on fresh tyres; the rival skipped the pit lap. Focus therefore carried
       one extra flying lap (~80–100 s), so ``rival_time - focus_time`` was
       ~−90 s (negative → undercut "not profitable").
       ``compute_field_undercut_value`` then fell through to
       ``simulate_undercut`` / T2-D, which is where the ~−0.5 s (or −1.2 s
       cap) bonus actually came from.

    2. ``laps_until_pit`` is ``estimated_pit_lap - current_lap`` from the
       cliff prior (HARD cliff 50 × race_frac, box at 0.85 of remaining).
       At the 5 inflections, a HARD first-stint car-ahead is mixed: Bahrain
       L31 ~7, Japan L26 ~9, Las Vegas L27 ~6 (T5 path); Belgium L29 and
       Italy L37 ~1 (T2-D gate in the caller, N ≤ 3). A rival who *just*
       pitted has small ``tyre_life`` → large N (T5 path). ``RivalPitEstimate``
       has no ``pit_compound`` field; next compound is inferred.

    3. Track position: only dirty air when ``gap_ahead - pit_loss < 0``
       (emerge *behind* a still-out rival). No term for emerging *ahead*
       after they box. Scoring was lap-time arithmetic only.

    Component A — missing. Component B — post-pit ``tyre_life=1`` was already
    set, but the two-phase window was not comparable, so the remaining-race
    delta was meaningless. Fix C: one remaining-race sim each (PIT_NOW vs
    PIT_LAP at current+N, rival post-pit resets to tyre_life=1 inside
    ``simulate``) plus ``TRACK_POSITION_VALUE`` when we emerge ahead.
    """
    _ = slopes  # simulate() uses track compound slopes
    from aris.physics.tyre_warmup import tyre_warmup_penalty
    from aris.simulate import ActionKind, StrategyAction

    current_lap = int(state.lap_number)
    pit_loss = float(circuit_pit_loss)

    N = max(0, int(getattr(rival, "laps_until_pit", 0)))
    rival_compound = str(getattr(rival, "compound", "HARD"))
    rival_tyre_age = int(getattr(rival, "tyre_life", 1) or 1)
    rival_code = str(getattr(rival, "driver_code", ""))
    rival_pit_compound = _infer_rival_expected_compound(
        rival_code, current_lap, getattr(state, "stints", {})
    )

    # One remaining-race sim each, same lap range (simulate() loops
    # range(lap_number, total_laps+1)). PIT_NOW / PIT_LAP reset tyre_life to 1
    # on the stop lap — rival post-pit is fresh on rival_pit_compound, not
    # inherited pre-pit age.
    focus_action = StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=pit_compound)
    try:
        focus_outcome = simulate(state, focus_action, deg_multiplier=deg_multiplier)
    except Exception:
        return 0.0
    focus_time = focus_outcome.total_race_time_s + tyre_warmup_penalty(pit_compound)

    # Dirty air vs a still-out rival after OUR stop. gap_ahead - pit_loss is
    # almost always negative inside the 22 s undercut window; this is a
    # surcharge, not the "emerge ahead after they box" term.
    gap_ahead = float(state.gap_ahead_s or 0.0)
    gap_after_our_stop = gap_ahead - pit_loss
    if gap_after_our_stop < 0:
        laps_stuck = min(3.0, abs(gap_after_our_stop) / 0.5)
        from aris.physics.traffic import DIRTY_AIR_PENALTY_PER_LAP
        focus_time += DIRTY_AIR_PENALTY_PER_LAP * laps_stuck

    rival_state = state.model_copy(
        update={
            "compound": rival_compound,
            "tyre_life": rival_tyre_age,
        }
    )
    rival_pit_lap = min(current_lap + N, int(state.total_laps))
    if N <= 0:
        rival_action = StrategyAction(
            kind=ActionKind.PIT_NOW, pit_compound=rival_pit_compound
        )
    else:
        rival_action = StrategyAction(
            kind=ActionKind.PIT_LAP,
            pit_lap=rival_pit_lap,
            pit_compound=rival_pit_compound,
        )
    try:
        rival_outcome = simulate(
            rival_state, rival_action, deg_multiplier=deg_multiplier
        )
    except Exception:
        return 0.0
    rival_time = rival_outcome.total_race_time_s + tyre_warmup_penalty(
        rival_pit_compound
    )

    # Positive = rival takes longer = we emerge ahead in remaining-race time.
    delta = rival_time - focus_time
    # Track position: time lead after both stops (pit losses already in both
    # sims) is worth clean air / not having to overtake — independent of the
    # lap-time arithmetic. Existing gap_after_our_stop is the wrong sign for
    # this (after OUR pit vs a still-out rival).
    if delta > 0:
        delta += TRACK_POSITION_VALUE
    return float(delta)


def compute_field_undercut_value(
    state: RaceState,
    rival_estimates: list,
    pit_compound: str,
    circuit_pit_loss: float,
    slopes: dict[str, float] | None,
    *,
    car_ahead_code: str | None,
    deg_multiplier: float = 1.0,
) -> tuple[float, str]:
    """Field-aware undercut vs the car ahead. Falls back to T2-D explicitly.

    When ``ARIS_FIELD_UNDERCUT=1``: uses ``_score_undercut_candidate()`` which
    is a remaining-race comparison (T5 rival-aware model). The flat −1.2 s cap
    is removed — the rival simulation is the signal, not a bonus constant.

    Dirty-air (0.15 s/lap when gap_ahead < 1s for 3+ laps) is folded into
    ``_score_undercut_candidate`` for the rival-aware path.  The legacy
    T2-D path still applies dirty_air as a one-shot on a winning field delta.
    """
    dirty_air = compute_dirty_air_penalty(list(state.gap_ahead_history or []))
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

    # T5 rival-aware scoring (replaces flat simulate_undercut + cap)
    rival_delta = _score_undercut_candidate(
        state, ahead, pit_compound, circuit_pit_loss, slopes,
        deg_multiplier=deg_multiplier,
    )
    # rival_delta > 0 → undercut is profitable; convert to a negative bonus so
    # the pit recommendation scores lower (faster) than stay-out.
    if rival_delta > 0:
        # No cap — the rival simulation is physically meaningful.
        return -rival_delta, "field"

    # Legacy path: simulate_undercut was not profitable via rival model.
    # Fall back to old physics delta with dirty-air but honour the cap.
    delta = simulate_undercut(
        state, ahead, pit_compound, circuit_pit_loss, slopes or {}
    )
    if delta < 0:
        return max(delta - dirty_air, FIELD_UNDERCUT_CAP), "field"
    return compute_undercut_bonus(state), "t2d"


def _undercut_bonus(state: RaceState, action: StrategyAction) -> float:
    if action.kind == ActionKind.STAY_OUT and not action.pit_laps:
        return 0.0
    if action.kind in (ActionKind.LIFT, ActionKind.BRAKE):
        return 0.0
    return compute_undercut_bonus(state)


def _get_available_compounds(state: RaceState) -> list[str]:
    """Pit compounds the simulator scores as genuine candidates.

    Dry list uses Pirelli allocation when present, otherwise SOFT/MEDIUM/HARD.
    Track state (T10-C) gates INTER/WET: DRY keeps slicks only; WET is wet
    compounds only; DAMP/CROSSOVER/DRYING offer slicks plus INTER.
    Suppresses a repeat of the current dry compound only when a longer stint
    still has a harder alternative and track temperature supports it.
    """
    alloc = getattr(state, "pirelli_allocation", None)
    base = list(alloc) if alloc else list(PIT_COMPOUNDS)
    order = list(PIT_COMPOUNDS)
    dry = [normalize_compound(c) for c in base]
    dry = [c for c in order if c in dry]
    if not dry:
        dry = list(PIT_COMPOUNDS)
    wet = ["INTERMEDIATE", "WET"]

    track_state = str(getattr(state, "track_state", "DRY") or "DRY").upper()
    if track_state == "DRY":
        candidates = list(dry)
    elif track_state == "WET":
        candidates = list(wet)
    elif track_state in ("DAMP", "CROSSOVER", "DRYING"):
        candidates = list(dry) + ["INTERMEDIATE"]
    else:
        candidates = list(dry)

    remaining = _laps_remaining(state)
    current = normalize_compound(state.compound)
    track_temp = getattr(state, "track_temp_c", None)

    dry_part = [c for c in candidates if c in PIT_COMPOUNDS]
    wet_part = [c for c in candidates if c not in PIT_COMPOUNDS]
    if track_state == "WET":
        return wet_part if wet_part else list(wet)

    if remaining < 15:
        return dry_part + wet_part
    if len(dry_part) <= 1 or current not in dry_part:
        return (dry_part if dry_part else list(PIT_COMPOUNDS)) + wet_part

    if current == "SOFT" and remaining >= 15:
        if track_temp is None or float(track_temp) >= 20.0:
            dry_part = [c for c in dry_part if c != "SOFT"]
    if current == "MEDIUM" and remaining >= 25:
        if "HARD" in dry_part and track_temp is not None and float(track_temp) > 25.0:
            dry_part = [c for c in dry_part if c != "MEDIUM"]
    out = dry_part if dry_part else list(PIT_COMPOUNDS)
    return out + wet_part


def pit_window_compound_times(state: RaceState, pit_lap: int) -> dict[str, float]:
    """Remaining-race sim time for a pit on ``pit_lap`` on each dry compound."""
    times: dict[str, float] = {}
    for compound in PIT_COMPOUNDS:
        action = StrategyAction(
            kind=ActionKind.PIT_LAP, pit_lap=pit_lap, pit_compound=compound
        )
        times[compound] = float(simulate(state, action).total_race_time_s)
    return times


MAX_REALISTIC_STINT_LAPS = 38
MIN_STINT_LAPS = 15


def _one_stop_covers_remaining(state: RaceState) -> bool:
    """True when a realistic current stint plus one stop covers the rest of the race."""
    remaining = _laps_remaining(state)
    tyre_life = max(1, int(state.tyre_life or 1))
    current_left = max(0, MAX_REALISTIC_STINT_LAPS - tyre_life)
    return remaining <= current_left + MAX_REALISTIC_STINT_LAPS


def _two_stop_stints_realistic(state: RaceState, pits: list[int]) -> bool:
    total = int(state.total_laps or 0)
    if not total:
        return False
    bounds = [int(state.lap_number)] + [int(p) for p in pits] + [total + 1]
    return all(b - a >= MIN_STINT_LAPS for a, b in zip(bounds, bounds[1:]))


def _inter_rain_confirmed(state: RaceState) -> bool:
    """Debounce INTER: require sustained rain or intensity, not a single DAMP tick."""
    mm = getattr(state, "rainfall_mm_per_lap", None)
    if mm is not None and float(mm) > INTER_RAIN_THRESHOLD_MM:
        return True
    track = str(getattr(state, "track_state", "") or "").upper()
    if track in {"WET", "CROSSOVER"}:
        return True
    raining = bool(getattr(state, "rainfall", False))
    session_rain = bool(getattr(state, "weather_rainfall", False))
    if raining and session_rain and track not in {"DAMP", "DRYING"}:
        return True
    return False


def _candidate_actions(state: RaceState) -> list[StrategyAction]:
    compounds = _get_available_compounds(state)
    actions: list[StrategyAction] = [
        StrategyAction(kind=ActionKind.STAY_OUT),
    ]
    for compound in compounds:
        actions.append(
            StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=compound)
        )
    for offset in (1, 2, 3, 5, 8):
        pit_lap = state.lap_number + offset
        if pit_lap > state.total_laps:
            continue
        for compound in compounds:
            actions.append(
                StrategyAction(
                    kind=ActionKind.PIT_LAP,
                    pit_lap=pit_lap,
                    pit_compound=compound,
                )
            )

    if not _one_stop_covers_remaining(state):
        mid = state.total_laps // 2
        for pits, compounds in (
            ([mid, state.total_laps - 8], ["MEDIUM", "HARD"]),
            ([mid - 5, mid + 10], ["SOFT", "HARD"]),
        ):
            valid = all(1 <= p <= state.total_laps for p in pits)
            if (
                valid
                and pits[0] >= state.lap_number
                and _two_stop_stints_realistic(state, pits)
            ):
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

    # DRY_WINDOW: only offer a dry compound switch when it is NOT actively
    # raining. If rainfall=True the track is still wet and a slick card is a
    # false positive (e.g. Australia 2025 ALB L47 — SC lap, rainfall=True,
    # team correctly stayed on INTER yet the unguarded path scored a dry pit).
    if remaining <= 10 and not bool(getattr(state, "rainfall", False)):
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
    scoring: str = "physics",
    cql_weight: float = 0.5,
) -> RecommendationResult:
    # include_tactical retained for API compatibility; hardcoded DRS/defend
    # deltas were removed in Phase C — line actions are scored via simulate().
    _ = include_tactical
    t0 = time.perf_counter()

    def _done(result: RecommendationResult) -> RecommendationResult:
        ms = (time.perf_counter() - t0) * 1000.0
        _LATENCY_SAMPLES_MS.append(ms)
        result.latency_ms = round(ms, 2)
        _log.debug(
            "recommend_latency_ms=%.2f lap=%s driver=%s mc_draws=%s",
            ms,
            state.lap_number,
            state.driver_code,
            mc_draws,
        )
        return result

    # T6: FSM phase config — drives pit loss, deg multiplier, and resets.
    phase_config = get_phase_config(state)

    # STRATEGY_RESET: RED_FLAG / STANDING_START → flush all strategies.
    # Return a sentinel dict so the frontend can display the reset banner.
    if phase_config.strategy_reset:
        return _done(
            _stamp_uncertainty(
                RecommendationResult(
                    state_lap=state.lap_number,
                    driver_code=state.driver_code,
                    compound=state.compound,
                    recommendations=[
                        Recommendation(
                            rank=1,
                            label="STRATEGY_RESET",
                            action=StrategyAction(kind=ActionKind.STAY_OUT),
                            delta_vs_stay_out_s=0.0,
                            mean_race_time_s=0.0,
                            confidence_std_s=0.0,
                            p10_delta_s=0.0,
                            p90_delta_s=0.0,
                            evidence=(
                                "Race phase: "
                                f"{phase_config.phase.name} — strategy recalculating"
                            ),
                            narration_context={
                                "action": "STRATEGY_RESET",
                                "reason": (
                                    "Race phase: "
                                    f"{phase_config.phase.name} — strategy recalculating"
                                ),
                                "phase": phase_config.phase.name,
                                "free_tyre_change": phase_config.free_tyre_change,
                            },
                        )
                    ],
                ),
                state,
            )
        )

    deg_mult = phase_config.deg_multiplier

    # T8: infer focus next-compound from stint history (2025+ year-gate).
    # T9: that inferred label still feeds undercut/overcut/narration via
    # state.pit_compound; the shortlist now scores every available dry
    # compound as a separate PIT_NOW / PIT_LAP candidate (see
    # _get_available_compounds). Empty stints keep state.pit_compound
    # (HARD) so the Zandvoort identity fixture is unchanged.
    #
    # Temporal filter: _build_stints_dict() reads ALL session laps upfront.
    # Filter to lap_start ≤ current lap to prevent future-pit leakage.
    if int(getattr(state, "year", 0)) >= 2025:
        race_frac = state.lap_number / max(1, state.total_laps)
        focus_stints = [
            s for s in state.stints.get(state.driver_code, [])
            if int(s.get("lap_start", 0)) <= state.lap_number
        ]
        inferred_compound = _infer_focus_compound(state, focus_stints, race_frac)
        if inferred_compound != state.pit_compound:
            state = state.model_copy(update={"pit_compound": inferred_compound})

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
    # T9: same weekend FP2 / prior / G1.5 overlay simulate() uses, so undercut
    # scoring does not silently fall back to YAML or G1.5 while ranking pits.
    slopes = {
        compound: get_deg_slope(
            compound,
            circuit_id=state.country,
            year=int(state.year) if state.year else None,
            round_number=int(state.round_no) if state.round_no else None,
        )
        for compound in ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")
    }
    circuit_pit_loss = float(track.pit_loss_s)

    # FSM: effective pit loss under SC/VSC/RED_FLAG phases.
    effective_pit_loss = (
        phase_config.pit_loss_override
        if phase_config.pit_loss_override >= 0
        else circuit_pit_loss * phase_config.pit_loss_multiplier
    )

    pit_compound = state.pit_compound  # already set to inferred_compound above

    field_bonus = 0.0
    undercut_source = "t2d"
    t2d = compute_undercut_bonus(state)
    if field_undercut_enabled() and field is not None:
        field_bonus, undercut_source = compute_field_undercut_value(
            state,
            estimates,
            pit_compound,
            effective_pit_loss,
            slopes,
            car_ahead_code=car_ahead_code,
            deg_multiplier=deg_mult,
        )
    else:
        field_bonus = t2d
        undercut_source = "t2d"

    # Rain-lock: on a wet compound in rain, suppress the dry shortlist.
    if should_stay_on_wet(state):
        candidates = _generate_wet_stay_candidates(
            state, slopes or {}, effective_pit_loss
        )
        if not any(_is_pure_stay(c) for c in candidates):
            candidates.append(_make_stay_out_card(state))
        return _done(
            _stamp_uncertainty(
                _rank_and_trim(candidates, state, top_k=top_k), state
            )
        )

    actions = list(_candidate_actions(state))
    if field is not None and field_overcut_enabled() and estimates:
        actions.extend(
            generate_overcut_candidates(
                state, estimates, slopes, effective_pit_loss
            )
        )

    for action in actions:
        outcome = simulate(state, action)  # always full degradation for remaining-race ranking
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
            mc = run_mc(state, action, n_draws=mc_draws)  # full degradation for MC ranking
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
        if (
            bonus < 0
            and undercut_source in {"t2d", "t2d_missing"}
            and state.gap_ahead_s is not None
        ):
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

    wet_on = should_recommend_inter(state, state.track_status) and _inter_rain_confirmed(
        state
    )
    if wet_on:
        mm = effective_rainfall_mm(state)
        remaining = max(int(state.laps_remaining), 1)
        wet_compounds = ["INTERMEDIATE"]
        if should_recommend_wet(state):
            wet_compounds.append("WET")
        for compound in wet_compounds:
            action = StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=compound)
            delta = wet_candidate_delta(
                mm, remaining, compound, pit_loss_s=effective_pit_loss
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

    mode = (scoring or "physics").strip().lower()
    if mode != "physics":
        from aris.models.cql import cql_score_candidates, load_cql_model

        q_net, norm = load_cql_model()
        if q_net is not None:
            cql_score_candidates(state, scored, q_net, norm)
            for rec in scored:
                if mode == "cql":
                    rec.rank_score = rec.cql_q_delta
                elif mode == "blend":
                    rec.rank_score = (
                        (1.0 - float(cql_weight)) * rec.delta_vs_stay_out_s
                        + float(cql_weight) * rec.cql_q_delta
                    )
                else:
                    rec.rank_score = rec.delta_vs_stay_out_s
        else:
            for rec in scored:
                rec.rank_score = rec.delta_vs_stay_out_s
    else:
        for rec in scored:
            rec.rank_score = rec.delta_vs_stay_out_s

    # Physics delta is the tie-break so same-compound cards keep timing order.
    scored.sort(key=lambda r: (r.rank_score, r.delta_vs_stay_out_s))
    if wet_on:
        wet_recs = [r for r in scored if r.wet_heuristic]
        if wet_recs:
            best_wet = min(wet_recs, key=lambda r: r.delta_vs_stay_out_s)
            track = str(getattr(state, "track_state", "") or "").upper()
            # Keep INTER/WET in the shortlist always; only force rank-1 under
            # sustained wet (WET/CROSSOVER) when the wet card clearly beats dry.
            # DAMP: compete normally — do not hijack rank-1 on a light shower.
            if track in {"WET", "CROSSOVER"}:
                dry_recs = [r for r in scored if not r.wet_heuristic]
                best_dry_delta = (
                    min(r.delta_vs_stay_out_s for r in dry_recs)
                    if dry_recs
                    else float("inf")
                )
                if best_wet.delta_vs_stay_out_s <= best_dry_delta - WET_FORCE_MARGIN_S:
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
    if os.getenv("ARIS_USE_MC") == "1":
        top = _maybe_rerank_mc(top, state)

    for i, rec in enumerate(top, start=1):
        rec.rank = i
        rec.delta_vs_stay_out_s = rec.rank_score

    top0 = top[0] if top else None
    if top0 is not None:
        act = top0.action
        _log.debug(
            "recommend_top lap=%s driver=%s label=%s pit_laps=%s track_state=%s rainfall=%s",
            state.lap_number,
            state.driver_code,
            top0.label,
            getattr(act, "pit_laps", None),
            getattr(state, "track_state", None),
            getattr(state, "rainfall", None),
        )

    return _done(
        _stamp_uncertainty(
            RecommendationResult(
                state_lap=state.lap_number,
                driver_code=state.driver_code,
                compound=state.compound,
                recommendations=top,
            ),
            state,
        )
    )
