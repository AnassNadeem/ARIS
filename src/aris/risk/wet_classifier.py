"""Track-state classifier (DRY / DAMP / CROSSOVER / WET / DRYING).

T10-C: 2024–2025 FastF1 weather has only five races with Rainfall=True on
≥5 laps, and none of those races has ≥50 wet laps. That is below the ML
threshold (≥8 wet races × ≥50 wet laps), so this module is a rule-based
scorer — not a fitted model. The five-class labels below are heuristics.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from aris.physics.tires import normalize_compound

_log = logging.getLogger(__name__)

WET_COMPOUNDS = frozenset({"INTERMEDIATE", "INTER", "WET"})
SLICK_COMPOUNDS = frozenset({"SOFT", "MEDIUM", "HARD"})
TRACK_STATES = ("DRY", "DAMP", "CROSSOVER", "WET", "DRYING")


def classify_track_state_rules(
    rain_flag: bool,
    rain_laps_last_5: int,
    track_temp_c: float,
    inter_on_track: bool,
    inter_pace_advantage_s: float = 0.0,
) -> tuple[str, float]:
    """Rule-based track state classifier. Used when training data is insufficient.

    Labels are a heuristic (C2), not observed ground truth. ``track_temp_c`` is
    accepted for the C1 feature contract and is unused by these rules.
    ``rain_laps_last_5 in [1, 3]`` is treated as the closed interval 1..3
    (C2), not the two-element Python list.
    """
    del track_temp_c
    n_rain = int(rain_laps_last_5)
    if not rain_flag and n_rain == 0 and not inter_on_track:
        return "DRY", 0.95

    if inter_on_track and n_rain == 0:
        return "DRYING", 0.80

    if n_rain >= 4:
        if inter_on_track and inter_pace_advantage_s > 1.5:
            return "WET", 0.85
        return "DAMP", 0.70

    if 1 <= n_rain <= 3:
        if inter_on_track and abs(inter_pace_advantage_s) < 1.0:
            return "CROSSOVER", 0.60
        return "DAMP", 0.65

    return "DRY", 0.80


def rain_laps_last_5(
    laps: pd.DataFrame | None,
    lap_number: int,
    *,
    current_rainfall: bool | None = None,
) -> int:
    """Count of laps in ``[lap-4, lap]`` where Rainfall was True."""
    start = max(1, int(lap_number) - 4)
    end = int(lap_number)
    flags: dict[int, bool] = {}
    if laps is not None and not laps.empty and "rainfall" in laps.columns:
        window = laps[
            (laps["lap_number"] >= start) & (laps["lap_number"] <= end)
        ]
        if not window.empty:
            grouped = window.groupby("lap_number")["rainfall"].any()
            flags = {int(k): bool(v) for k, v in grouped.items()}
    if current_rainfall is not None:
        flags[end] = bool(current_rainfall) or flags.get(end, False)
    return int(sum(1 for lap in range(start, end + 1) if flags.get(lap, False)))


def inter_field_stats(
    all_laps: pd.DataFrame | None, lap_number: int
) -> tuple[bool, float]:
    """INTER/WET on the current lap, and slick − INTER median pace (s).

    Positive advantage means INTER cars are faster. When the field has
    abandoned slicks, advantage is set to +3.0 s so the WET rule can fire
    without a slick comparison. Returns ``(False, 0.0)`` when the join is
    empty — no extra engineering beyond ``fetch_all_laps``.
    """
    if all_laps is None or all_laps.empty:
        return False, 0.0
    if "compound" not in all_laps.columns or "lap_number" not in all_laps.columns:
        return False, 0.0
    at = all_laps[all_laps["lap_number"] == int(lap_number)]
    if at.empty:
        return False, 0.0
    compounds = at["compound"].map(normalize_compound)
    inter_mask = compounds.isin(WET_COMPOUNDS)
    slick_mask = compounds.isin(SLICK_COMPOUNDS)
    inter_on = bool(inter_mask.any())
    if not inter_on:
        return False, 0.0
    if "lap_time_s" not in at.columns:
        return True, 0.0
    inter_times = at.loc[inter_mask, "lap_time_s"].dropna()
    slick_times = at.loc[slick_mask, "lap_time_s"].dropna()
    if inter_times.empty:
        return True, 0.0
    if slick_times.empty:
        # Whole field on wet tyres — no slick baseline; treat as a clear INTER advantage.
        return True, 3.0
    return True, float(slick_times.median() - inter_times.median())


def attach_track_state(
    state: Any,
    *,
    laps: pd.DataFrame | None = None,
    all_laps: pd.DataFrame | None = None,
) -> Any:
    """Populate ``track_state`` / ``track_state_confidence`` on a RaceState copy."""
    rain_flag = bool(getattr(state, "rainfall", False))
    n_rain = rain_laps_last_5(
        laps, int(state.lap_number), current_rainfall=rain_flag
    )
    inter_on, advantage = inter_field_stats(all_laps, int(state.lap_number))
    temp = getattr(state, "track_temp_c", None)
    track_temp = float(temp) if temp is not None else 25.0
    label, conf = classify_track_state_rules(
        rain_flag=rain_flag,
        rain_laps_last_5=n_rain,
        track_temp_c=track_temp,
        inter_on_track=inter_on,
        inter_pace_advantage_s=advantage,
    )
    return state.model_copy(
        update={"track_state": label, "track_state_confidence": float(conf)}
    )
