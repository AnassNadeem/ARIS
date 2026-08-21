"""Wet / intermediate heuristic — uncalibrated, not a fitted deg model.

Does not use G1.5 dry slopes or FastF1 wet-slope fits. Ranking numbers are
order-of-magnitude only; live radio must say so.
"""

from __future__ import annotations

from aris.physics.tires import normalize_compound

INTER_PACE_LOSS_VS_SLICK = 3.0
WET_PACE_LOSS_VS_SLICK = 8.0
RAIN_SLICK_PENALTY_PER_MM = 2.0
INTER_RAIN_THRESHOLD_MM = 0.5
WET_RAIN_THRESHOLD_MM = 2.0
BOOLEAN_RAIN_MM = 1.2  # when only session_weather.rainfall is set
MIN_LAPS_FOR_INTER = 8
SLICK = frozenset({"SOFT", "MEDIUM", "HARD"})
WET_COMPOUNDS = frozenset({"INTERMEDIATE", "WET"})


def effective_rainfall_mm(state) -> float:
    mm = getattr(state, "rainfall_mm_per_lap", None)
    if mm is not None:
        return float(mm)
    if getattr(state, "weather_rainfall", None) is True:
        return BOOLEAN_RAIN_MM
    return 0.0


def _field_on_wet(field) -> bool:
    if field is None:
        return False
    for row in getattr(field, "standings", []) or []:
        if normalize_compound(getattr(row, "compound", None)) in WET_COMPOUNDS:
            return True
    return False


def _is_red(state) -> bool:
    status = str(getattr(state, "track_status", None) or "")
    return "5" in status


def should_recommend_inter(state, field=None) -> bool:
    """True when slicks are the wrong tyre given rain / field already wet.

    Ignores FastF1 track_status 4/6/7 (SC/VSC) as a wet signal. Status 5 is
    a red flag, not extreme wet.
    """
    compound = normalize_compound(getattr(state, "compound", None))
    if compound in WET_COMPOUNDS:
        return False
    if compound not in SLICK:
        return False
    if int(getattr(state, "laps_remaining", 0) or 0) < MIN_LAPS_FOR_INTER:
        return False
    if _is_red(state):
        return False
    mm = getattr(state, "rainfall_mm_per_lap", None)
    raining = (
        (mm is not None and float(mm) > INTER_RAIN_THRESHOLD_MM)
        or getattr(state, "weather_rainfall", None) is True
        or _field_on_wet(field)
    )
    return bool(raining)


def should_recommend_wet(state) -> bool:
    """Full wet only for heavy rain or already on INTER with rain still on."""
    if _is_red(state):
        return False
    mm = effective_rainfall_mm(state)
    compound = normalize_compound(getattr(state, "compound", None))
    if mm >= WET_RAIN_THRESHOLD_MM:
        return True
    raining = mm > INTER_RAIN_THRESHOLD_MM or getattr(state, "weather_rainfall", None) is True
    return compound == "INTERMEDIATE" and raining


def wet_candidate_delta(
    rainfall_mm_per_lap: float,
    laps_remaining: int,
    compound: str = "INTERMEDIATE",
    *,
    pit_loss_s: float = 0.0,
) -> float:
    """Seconds vs staying on slicks in the rain. Negative = the wet tyre is faster.

    Uncalibrated. Do not treat as a fitted model.
    """
    slick_penalty = float(rainfall_mm_per_lap) * RAIN_SLICK_PENALTY_PER_MM
    key = normalize_compound(compound)
    wet_penalty = WET_PACE_LOSS_VS_SLICK if key == "WET" else INTER_PACE_LOSS_VS_SLICK
    return (wet_penalty - slick_penalty) * int(laps_remaining) + float(pit_loss_s)
