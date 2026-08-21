"""Lights-out sequential ablation (48-race prewrite). Analysis only.

Does not change G1.5, T2-A, ``recommend()``, or Zandvoort default labels.
Position-delta is identity-safe time-rank, not FIA points.

Constraints, one at a time then stacked:
  1. team start compound
  2. team first-stop lap
  3. team pit count
  4. drop SC/VSC pits from *stop-count comparison only* (not a schedule force)

Optional fuel ±5 kg / out-lap 0 vs 1.5 vs 3 s lives in the analysis script
and must not be written back as a new constant.
"""

from __future__ import annotations

from typing import Any

from aris.eval.backtest import _delta_stats, is_major_disruption
from aris.eval.postrace import PitSchedule, bias_cancelled_delta, simulate_schedule
from aris.state import RaceState

VARIANT_ORDER = (
    "baseline",
    "start_compound",
    "first_stop",
    "pit_count",
    "stacked",
)


def _copy(sched: PitSchedule) -> PitSchedule:
    return PitSchedule(
        pit_laps=list(sched.pit_laps),
        pit_compounds=list(sched.pit_compounds),
        start_compound=sched.start_compound,
    )


def _monotonic(laps: list[int]) -> list[int]:
    out: list[int] = []
    prev = 0
    for lap in laps:
        nxt = max(int(lap), prev + 1)
        out.append(nxt)
        prev = nxt
    return out


def force_start_compound(aris: PitSchedule, team: PitSchedule) -> PitSchedule:
    out = _copy(aris)
    out.start_compound = team.start_compound
    return out


def force_first_stop(aris: PitSchedule, team: PitSchedule) -> PitSchedule:
    """Replace ARIS's first stop lap with the team's. No-op if the team never boxed."""
    if not team.pit_laps:
        return _copy(aris)
    out = _copy(aris)
    team_lap = int(team.pit_laps[0])
    if team.pit_compounds:
        team_compound = team.pit_compounds[0]
    elif out.pit_compounds:
        team_compound = out.pit_compounds[0]
    else:
        team_compound = "HARD"
    if not out.pit_laps:
        out.pit_laps = [team_lap]
        out.pit_compounds = [team_compound]
        return out
    out.pit_laps[0] = team_lap
    out.pit_laps = _monotonic(out.pit_laps)
    return out


def force_pit_count(aris: PitSchedule, team: PitSchedule) -> PitSchedule:
    """Match the team's number of stops, keeping ARIS compounds where possible."""
    n_t, n_a = len(team.pit_laps), len(aris.pit_laps)
    out = _copy(aris)
    if n_t == n_a:
        return out
    if n_t < n_a:
        out.pit_laps = out.pit_laps[:n_t]
        out.pit_compounds = out.pit_compounds[:n_t]
        return out
    extra_laps = list(team.pit_laps[n_a:])
    extra_compounds = list(team.pit_compounds[n_a:]) if len(team.pit_compounds) >= n_t else (
        ["HARD"] * (n_t - n_a)
    )
    if len(extra_compounds) < len(extra_laps):
        extra_compounds = extra_compounds + ["HARD"] * (len(extra_laps) - len(extra_compounds))
    out.pit_laps = _monotonic(out.pit_laps + extra_laps)
    out.pit_compounds = out.pit_compounds + extra_compounds[: len(extra_laps)]
    return out


def stacked_constraints(aris: PitSchedule, team: PitSchedule) -> PitSchedule:
    """Start compound, then first-stop lap, then pit count."""
    return force_pit_count(force_first_stop(force_start_compound(aris, team), team), team)


def extra_stops(aris: PitSchedule, team: PitSchedule) -> int:
    return len(team.pit_laps) - len(aris.pit_laps)


def extra_stops_ex_sc_vsc(
    aris: PitSchedule, team: PitSchedule, sc_vsc_pit_laps: list[int]
) -> int:
    """Stop-count comparison after dropping team SC/VSC pits. Not a schedule force."""
    sc = {int(x) for x in sc_vsc_pit_laps}
    team_green = [p for p in team.pit_laps if int(p) not in sc]
    return len(team_green) - len(aris.pit_laps)


def apply_variant(name: str, aris: PitSchedule, team: PitSchedule) -> PitSchedule:
    if name == "baseline":
        return _copy(aris)
    if name == "start_compound":
        return force_start_compound(aris, team)
    if name == "first_stop":
        return force_first_stop(aris, team)
    if name == "pit_count":
        return force_pit_count(aris, team)
    if name == "stacked":
        return stacked_constraints(aris, team)
    raise ValueError(f"unknown ablation variant {name!r}")


def score_schedules(
    field_times: dict[str, float],
    driver_code: str,
    *,
    actual_time_s: float,
    start_state: RaceState,
    aris: PitSchedule,
    team: PitSchedule,
    pit_status_by_lap: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Identity-safe position-delta. Do not map this to FIA points."""
    aris_sim = simulate_schedule(
        start_state, aris, pit_status_by_lap=pit_status_by_lap
    )
    team_sim = simulate_schedule(
        start_state, team, pit_status_by_lap=pit_status_by_lap
    )
    aris_pos, actual_rank, delta = bias_cancelled_delta(
        field_times,
        driver_code,
        actual_time_s=actual_time_s,
        aris_sim_s=float(aris_sim),
        team_sim_s=float(team_sim),
    )
    return {
        "aris_sim_s": float(aris_sim),
        "team_sim_s": float(team_sim),
        "aris_finish_pos": aris_pos,
        "actual_time_rank": actual_rank,
        "position_delta": delta,
        "aris_pits": list(aris.pit_laps),
        "team_pits": list(team.pit_laps),
        "start_compound": aris.start_compound,
    }


def ablation_row(
    *,
    field_times: dict[str, float],
    driver_code: str,
    actual_time_s: float,
    start_state: RaceState,
    aris: PitSchedule,
    team: PitSchedule,
    focus_laps,
    sc_vsc_pit_laps: list[int] | None = None,
    year: int | None = None,
    gp: str | None = None,
    round_no: int | None = None,
) -> dict[str, Any]:
    disrupted = is_major_disruption(focus_laps)
    sc_pits = list(sc_vsc_pit_laps or [])
    variants: dict[str, Any] = {}
    for name in VARIANT_ORDER:
        forced = apply_variant(name, aris, team)
        scored = score_schedules(
            field_times,
            driver_code,
            actual_time_s=actual_time_s,
            start_state=start_state,
            aris=forced,
            team=team,
        )
        variants[name] = scored
    return {
        "year": year,
        "gp": gp,
        "round_no": round_no,
        "driver_code": driver_code,
        "major_disruption": disrupted,
        "extra_stops": extra_stops(aris, team),
        "extra_stops_ex_sc_vsc": extra_stops_ex_sc_vsc(aris, team, sc_pits),
        "n_team_pits_sc_vsc": len(sc_pits),
        "variants": variants,
        "not_fia_points": True,
    }


def _split_stats(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    def _vals(name: str, predicate) -> list[float]:
        out: list[float] = []
        for row in rows:
            delta = (row.get("variants") or {}).get(name, {}).get("position_delta")
            if delta is None:
                continue
            if predicate(row):
                out.append(float(delta))
        return out

    all_stats = _delta_stats(_vals(variant, lambda r: True))
    clean = _delta_stats(_vals(variant, lambda r: not r.get("major_disruption")))
    disrupted = _delta_stats(_vals(variant, lambda r: bool(r.get("major_disruption"))))
    paired_base: list[float] = []
    paired_var: list[float] = []
    for row in rows:
        b = (row.get("variants") or {}).get("baseline", {}).get("position_delta")
        v = (row.get("variants") or {}).get(variant, {}).get("position_delta")
        if b is None or v is None:
            continue
        paired_base.append(float(b))
        paired_var.append(float(v))
    if not paired_var:
        d_mean = None
        base_mean = None
    elif variant == "baseline":
        d_mean = 0.0
        base_mean = sum(paired_base) / len(paired_base)
    else:
        base_mean = sum(paired_base) / len(paired_base)
        d_mean = sum(paired_var) / len(paired_var) - base_mean
    return {
        "all": all_stats,
        "clean": clean,
        "disrupted": disrupted,
        "delta_vs_baseline_mean": d_mean,
        "baseline_mean": base_mean,
    }


def summarize_ablation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    extra = [float(r["extra_stops"]) for r in rows if r.get("extra_stops") is not None]
    extra_ex = [
        float(r["extra_stops_ex_sc_vsc"])
        for r in rows
        if r.get("extra_stops_ex_sc_vsc") is not None
    ]
    return {
        "n_races": len(rows),
        "n_clean": sum(1 for r in rows if not r.get("major_disruption")),
        "n_disrupted": sum(1 for r in rows if r.get("major_disruption")),
        "extra_stops": _delta_stats(extra),
        "extra_stops_ex_sc_vsc": _delta_stats(extra_ex),
        "variants": {name: _split_stats(rows, name) for name in VARIANT_ORDER},
        "kill_gate": (
            "do not change G1.5, T2-A, or default Zandvoort labels; "
            "if first-stop force removes most of −1.73, stop chasing fuel/out-lap"
        ),
        "not_fia_points": True,
    }
