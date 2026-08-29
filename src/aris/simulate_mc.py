"""Vectorised remaining-race Monte Carlo. No Python loop over scenarios."""

from __future__ import annotations

import numpy as np

SC_LAP_PENALTY_S = 5.0


def _sc_active_mask(sc_events: np.ndarray, sc_duration_laps: int) -> np.ndarray:
    """Expand per-lap SC starts into a duration window. Shape (n_scenarios, laps)."""
    duration = max(int(sc_duration_laps), 1)
    active = sc_events.copy()
    for offset in range(1, duration):
        active[:, offset:] |= sc_events[:, :-offset]
    return active


def _lap_times_matrix(
    n_scenarios: int,
    laps_remaining: int,
    base_lap_time_s: float,
    deg_slope: float,
    tyre_age_start: int,
    pit_lap: int | None,
    pit_compound_slope: float,
    pit_loss_s: float,
    warmup_penalty_s: float,
    noise: np.ndarray,
    sc_events: np.ndarray,
    sc_duration_laps: int,
    sc_pit_loss_multiplier: float,
) -> np.ndarray:
    """Green + SC + pit lap times, shape (n_scenarios, laps_remaining)."""
    laps = np.arange(int(laps_remaining), dtype=np.int32)
    ages = tyre_age_start + laps
    slopes = np.full(laps_remaining, float(deg_slope), dtype=float)
    bases = np.full(laps_remaining, float(base_lap_time_s), dtype=float)

    if pit_lap is not None and 0 <= int(pit_lap) < laps_remaining:
        p = int(pit_lap)
        # In-lap (l == p) stays on the old tyre; stint resets after the stop.
        post = laps > p
        ages = np.where(post, laps - p - 1, ages)
        slopes = np.where(post, float(pit_compound_slope), slopes)
        outlap = post & (ages == 0)
        bases = np.where(outlap, bases + float(warmup_penalty_s), bases)

    lap_times = bases[None, :] + slopes[None, :] * ages[None, :] + noise
    sc_active = _sc_active_mask(sc_events, sc_duration_laps)
    lap_times = lap_times + SC_LAP_PENALTY_S * sc_active.astype(float)

    # pit_loss_s is a delta vs a green lap (ARIS YAML), not a full lap replacement.
    if pit_lap is not None and 0 <= int(pit_lap) < laps_remaining:
        p = int(pit_lap)
        pit_loss = np.full(n_scenarios, float(pit_loss_s), dtype=float)
        pit_loss[sc_active[:, p]] *= float(sc_pit_loss_multiplier)
        lap_times[:, p] = lap_times[:, p] + pit_loss

    return lap_times


def sample_remaining_race(
    n_scenarios: int,
    laps_remaining: int,
    base_lap_time_s: float,
    deg_slope: float,
    deg_sigma: float,
    tyre_age_start: int,
    pit_lap: int | None,
    pit_compound_slope: float,
    pit_loss_s: float,
    warmup_penalty_s: float,
    p_sc_per_lap: float,
    sc_duration_laps: int = 3,
    sc_pit_loss_multiplier: float = 0.50,
    seed: int | None = None,
    *,
    noise: np.ndarray | None = None,
    sc_events: np.ndarray | None = None,
) -> np.ndarray:
    """
    Returns array of shape (n_scenarios,) containing total remaining race times.

    Fully vectorised: all scenarios computed in parallel as NumPy operations.

    Lap times are modelled as:
    lap_time[l] = base_lap_time + deg_slope * tyre_age[l] + noise[l]
    where noise ~ N(0, deg_sigma)
    """
    n = int(n_scenarios)
    remaining = int(laps_remaining)
    if n <= 0:
        return np.zeros(0, dtype=float)
    if remaining <= 0:
        return np.zeros(n, dtype=float)

    rng = np.random.default_rng(seed)
    if noise is None:
        noise = rng.normal(0.0, float(deg_sigma), size=(n, remaining))
    if sc_events is None:
        sc_events = rng.random(size=(n, remaining)) < float(p_sc_per_lap)

    lap_times = _lap_times_matrix(
        n_scenarios=n,
        laps_remaining=remaining,
        base_lap_time_s=float(base_lap_time_s),
        deg_slope=float(deg_slope),
        tyre_age_start=int(tyre_age_start),
        pit_lap=pit_lap,
        pit_compound_slope=float(pit_compound_slope),
        pit_loss_s=float(pit_loss_s),
        warmup_penalty_s=float(warmup_penalty_s),
        noise=noise,
        sc_events=sc_events,
        sc_duration_laps=int(sc_duration_laps),
        sc_pit_loss_multiplier=float(sc_pit_loss_multiplier),
    )
    return lap_times.sum(axis=1)


def compare_actions_mc(
    actions: list[dict],
    base_state: dict,
    n_scenarios: int = 200,
    warmup_penalties: dict | None = None,
    seed: int | None = 42,
) -> list[dict]:
    """
    Run Monte Carlo for each action and return ranked results.

    Shared noise and SC draws across actions so ``p_best`` is a fair
    paired comparison. Returns list of dicts, sorted by expected_total_s
    (ascending).
    """
    remaining = max(int(base_state.get("laps_remaining") or 0), 0)
    n = int(n_scenarios)
    deg_sigma = float(base_state.get("deg_sigma") or 0.0)
    p_sc = float(base_state.get("p_sc_per_lap") or 0.0)
    base_lap = float(base_state.get("base_lap_time") or 90.0)
    deg_slope = float(base_state.get("deg_slope") or 0.03)
    tyre_age = int(base_state.get("tyre_age") or 1)
    sc_duration = int(base_state.get("sc_duration_laps") or 3)
    sc_mult = float(base_state.get("sc_pit_loss_multiplier") or 0.50)
    warmups = warmup_penalties or {}

    rng = np.random.default_rng(seed)
    if remaining <= 0 or n <= 0 or not actions:
        return [
            {
                "action": str(a.get("name") or a.get("action") or "stay"),
                "expected_total_s": 0.0,
                "p10_s": 0.0,
                "p90_s": 0.0,
                "p_best": 1.0 / max(len(actions), 1),
                "delta_vs_stay": 0.0,
            }
            for a in actions
        ]

    noise = rng.normal(0.0, deg_sigma, size=(n, remaining))
    sc_events = rng.random(size=(n, remaining)) < p_sc

    totals: list[np.ndarray] = []
    names: list[str] = []
    stay_idx: int | None = None
    for i, action in enumerate(actions):
        name = str(action.get("name") or action.get("action") or f"action_{i}")
        names.append(name)
        pit_lap = action.get("pit_lap")
        if pit_lap is not None:
            pit_lap = int(pit_lap)
        compound = str(action.get("compound") or "")
        warmup = float(
            warmups.get(compound, warmups.get("INTER", 0.0) if compound == "INTERMEDIATE" else 0.0)
        )
        if pit_lap is None:
            stay_idx = i if stay_idx is None else stay_idx
            warmup = 0.0
        times = sample_remaining_race(
            n_scenarios=n,
            laps_remaining=remaining,
            base_lap_time_s=base_lap,
            deg_slope=deg_slope,
            deg_sigma=deg_sigma,
            tyre_age_start=tyre_age,
            pit_lap=pit_lap,
            pit_compound_slope=float(action.get("pit_compound_slope") or deg_slope),
            pit_loss_s=float(action.get("pit_loss") or 0.0),
            warmup_penalty_s=warmup,
            p_sc_per_lap=p_sc,
            sc_duration_laps=sc_duration,
            sc_pit_loss_multiplier=sc_mult,
            noise=noise,
            sc_events=sc_events,
        )
        totals.append(times)

    stacked = np.stack(totals, axis=0)  # (n_actions, n_scenarios)
    best = stacked.argmin(axis=0)
    stay_totals = stacked[stay_idx] if stay_idx is not None else stacked[0]
    stay_expected = float(stay_totals.mean())

    rows: list[dict] = []
    for i, name in enumerate(names):
        arr = stacked[i]
        expected = float(arr.mean())
        rows.append(
            {
                "action": name,
                "expected_total_s": expected,
                "p10_s": float(np.percentile(arr, 10)),
                "p90_s": float(np.percentile(arr, 90)),
                "p_best": float(np.mean(best == i)),
                "delta_vs_stay": expected - stay_expected,
            }
        )
    rows.sort(key=lambda r: r["expected_total_s"])
    return rows
