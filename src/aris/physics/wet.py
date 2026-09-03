"""Wet / intermediate heuristic — uncalibrated, not a fitted deg model.

Does not use G1.5 dry slopes or FastF1 wet-slope fits. Ranking numbers are
order-of-magnitude only; live radio must say so.

Rain detection uses FastF1 ``weather_data['Rainfall']`` (boolean, sampled
roughly every minute / 3–5 laps). Track status ``4`` is Safety Car, not rain.
"""

from __future__ import annotations

import pandas as pd

from aris.physics.tires import normalize_compound

# 2024 Brazil (Interlagos): VER (and the field) never ran slicks — INTER/WET
# only. No in-race slick-to-inter transition exists, so that race cannot
# anchor INTER vs slick. 2024 Britain, Rainfall=True: INTER mean 101.29 s vs
# slick 90.92 s (INTER +10.4 s, slicks still faster in light rain). That
# number is not the live advantage — the heuristic only fires when we already
# treat slicks as the wrong tyre. Conservative remaining-lap advantage is the
# less-negative bound of the original T3-E band.
INTER_VS_SLICK_ADV_LOW = -1.5
INTER_VS_SLICK_ADV_HIGH = -3.0
INTER_VS_SLICK_ADV = INTER_VS_SLICK_ADV_LOW  # conservative default
WET_VS_SLICK_ADV = -4.0

# Legacy penalty model (kept for mm-based callers / tests).
INTER_PACE_LOSS_VS_SLICK = 3.0
WET_PACE_LOSS_VS_SLICK = 8.0
RAIN_SLICK_PENALTY_PER_MM = 2.0
INTER_RAIN_THRESHOLD_MM = 0.5
WET_RAIN_THRESHOLD_MM = 2.0
BOOLEAN_RAIN_MM = 1.2  # when only the per-lap rainfall boolean is set
MIN_LAPS_FOR_INTER = 8
# Only force INTER/WET to rank-1 when it beats the best dry card by this much
# under WET/CROSSOVER. Prevents a single DAMP tick from hijacking rank-1.
WET_FORCE_MARGIN_S = 5.0
SLICK = frozenset({"SOFT", "MEDIUM", "HARD"})
WET_COMPOUNDS = frozenset({"INTERMEDIATE", "INTER", "WET"})


def nearest_rainfall(weather_data, lap_start_time) -> bool:
    """Boolean rainfall from the FastF1 weather sample closest to lap start.

    FastF1 ``weather_data['Rainfall']`` is a boolean. ``Time`` is a timedelta
    from session start, same epoch as ``laps['LapStartTime']``. Empty or
    missing weather defaults to False (dry).
    """
    if weather_data is None:
        return False
    try:
        if getattr(weather_data, "empty", True):
            return False
    except Exception:
        return False
    if "Rainfall" not in weather_data.columns:
        return False

    def _secs(value) -> float | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if hasattr(value, "total_seconds"):
            return float(value.total_seconds())
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    target = _secs(lap_start_time)
    if target is None or "Time" not in weather_data.columns:
        series = weather_data["Rainfall"].fillna(False)
        if series.empty:
            return False
        return bool(series.iloc[-1])

    times = weather_data["Time"].map(_secs)
    valid = times.dropna()
    if valid.empty:
        return False
    idx = (valid - target).abs().idxmin()
    val = weather_data.loc[idx, "Rainfall"]
    try:
        if pd.isna(val):
            return False
    except (TypeError, ValueError):
        pass
    return bool(val)


def effective_rainfall_mm(state) -> float:
    mm = getattr(state, "rainfall_mm_per_lap", None)
    if mm is not None:
        return float(mm)
    if getattr(state, "rainfall", False):
        return BOOLEAN_RAIN_MM
    return 0.0


def _is_red(state, track_status: str | None = None) -> bool:
    status = str(
        track_status
        if track_status is not None
        else (getattr(state, "track_status", None) or "")
    )
    return "5" in status


def should_recommend_inter(
    state,
    track_status: str | None = None,
    field=None,
) -> bool:
    """Recommend intermediate tyres when rain conditions are detected.

    Rain detection (in order of reliability):
    1. state.rainfall is True — from FastF1 weather_data['Rainfall']
       This is the primary signal. Boolean, sampled per lap.
    2. state.compound is already INTER or WET — field has already
       switched. Do not recommend switching again.
    3. track_status '6' — VSC sometimes correlates with wet track
       but is not reliable alone. Use only as supporting signal.

    DO NOT use track_status '4' (SC) as a rain indicator.
    SC is deployed for many reasons — debris, accidents, etc.
    A dry SC must not trigger an intermediate recommendation.

    Conservative guard: only recommend INTER if at least 8 laps
    remaining AND current compound is a dry slick.
    """
    del field  # field-on-wet is not a rain signal (SC-era false positive)
    compound = normalize_compound(getattr(state, "compound", None))
    if compound in WET_COMPOUNDS:
        return False
    if compound not in SLICK:
        return False

    remaining = int(getattr(state, "laps_remaining", 0) or 0)
    total = int(getattr(state, "total_laps", 0) or 0)
    lap = int(getattr(state, "lap_number", 0) or 0)
    if total:
        remaining = max(remaining, total - lap)
    if remaining < MIN_LAPS_FOR_INTER:
        return False
    if _is_red(state, track_status):
        return False

    is_raining = bool(getattr(state, "rainfall", False))
    mm = getattr(state, "rainfall_mm_per_lap", None)
    if mm is not None and float(mm) > INTER_RAIN_THRESHOLD_MM:
        is_raining = True

    status = str(
        track_status
        if track_status is not None
        else (getattr(state, "track_status", None) or "")
    )
    # VSC ('6') is supporting only — never sufficient without rainfall.
    _ = "6" in status

    if not is_raining:
        return False
    return True


def should_stay_on_wet(state) -> bool:
    """True when the car is on a wet compound in rain and should not switch to slicks.

    Mirror of ``should_recommend_inter``: that fires on slicks in rain (switch
    to wet); this fires on INTER/WET in rain (stay on wet). Track status ``4``
    is Safety Car, not rain.

    Primary rain bit is per-lap ``state.rainfall``. Session-level
    ``weather_rainfall`` alone must not keep the INTER lock after rain has
    stopped on a per-lap basis — it is only a tiebreaker when ``rainfall`` is
    ambiguous (``None``). A dry SC (no rain bits) still switches to slick.
    """
    compound = normalize_compound(getattr(state, "compound", None))
    if compound not in WET_COMPOUNDS:
        return False
    rain_bit = getattr(state, "rainfall", None)
    if rain_bit is None:
        raining = bool(getattr(state, "weather_rainfall", False))
    else:
        raining = bool(rain_bit)
    if not raining:
        return False
    remaining = int(getattr(state, "laps_remaining", 0) or 0)
    total = int(getattr(state, "total_laps", 0) or 0)
    lap = int(getattr(state, "lap_number", 0) or 0)
    if remaining < 5:
        return False
    if total and (total - lap) < 5:
        return False
    if _is_red(state):
        return False
    return True


def wet_stay_delta(state, laps_remaining: int) -> float:
    """Per-remaining-lap penalty for switching to slick while it is still raining.

    Positive = slick costs this many seconds vs staying on the current wet
    compound. Conservative: INTER_VS_SLICK_ADV_LOW (light rain, slick only
    slightly disadvantaged). ``state`` is accepted for API symmetry.
    """
    del state
    slick_penalty_per_lap = abs(INTER_VS_SLICK_ADV_LOW)  # 1.5 s/lap
    return float(slick_penalty_per_lap) * int(laps_remaining)


def should_recommend_wet(state) -> bool:
    """Full wet only for heavy rain or already on INTER with rain still on."""
    if _is_red(state):
        return False
    mm = effective_rainfall_mm(state)
    compound = normalize_compound(getattr(state, "compound", None))
    if mm >= WET_RAIN_THRESHOLD_MM:
        return True
    raining = bool(getattr(state, "rainfall", False)) or mm > INTER_RAIN_THRESHOLD_MM
    return compound in {"INTERMEDIATE", "INTER"} and raining


def wet_candidate_delta(
    rainfall_mm_per_lap: float,
    laps_remaining: int,
    compound: str = "INTERMEDIATE",
    *,
    pit_loss_s: float = 0.0,
) -> float:
    """Seconds vs staying on slicks in the rain. Negative = the wet tyre is faster.

    Default INTER advantage is INTER_VS_SLICK_ADV_LOW from 2024 Brazil
    (conservative). mm argument is retained for callers; when mm is 0 the
    empirical INTER/WET constants still apply so a boolean-rain card is
    not scored as a slick.
    """
    del rainfall_mm_per_lap  # empirical per-lap adv replaces the mm penalty model
    key = normalize_compound(compound)
    per_lap = WET_VS_SLICK_ADV if key == "WET" else INTER_VS_SLICK_ADV
    return float(per_lap) * int(laps_remaining) + float(pit_loss_s)
