"""Race state snapshot for strategy simulation."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from pydantic import BaseModel
from sqlalchemy import text

_log = logging.getLogger(__name__)

from aris.io import db
from aris.models.features import estimate_fuel_kg
from aris.tracks import load_track_config

DEFAULT_TOTAL_LAPS = 57
DEFAULT_TRACK_NAME = "Bahrain"

# FastF1 TrackStatus codes that contaminate pace used by lag features / What-if.
# 4 = Safety Car, 6 = VSC deployed, 7 = VSC ending. Multi-code strings like "24"
# (yellow + SC) also match via substring.
_SC_VSC_CODES = ("4", "6", "7")
SC_PACE_CAVEAT = (
    "based on Safety Car-affected recent pace — lower confidence"
)
# Effective pit-loss vs green-flag YAML pit_loss. SC delta is ~40s/lap so net
# stop cost is ~6–7s (6.5/18.5 ≈ 0.35). VSC delta is smaller (~10/18.5 ≈ 0.55).
SC_PIT_LOSS_MULT = 0.35
VSC_PIT_LOSS_MULT = 0.55


def track_status_is_sc_vsc(status: str | None) -> bool:
    """True when a FastF1 TrackStatus string indicates SC / VSC involvement."""
    if status is None:
        return False
    s = str(status).strip()
    if not s or s in ("1", "None", "nan"):
        return False
    return any(code in s for code in _SC_VSC_CODES)


def sc_vsc_pit_multiplier(
    status: str | None, circuit_key: str | None = None
) -> float | None:
    """Pit-loss multiplier for the current lap, or None on green.

    FastF1 may emit multi-code strings (``24`` = yellow + SC). Prefer SC (4)
    over VSC (6) / VSC-ending (7) when both appear.

    Default is the napkin 0.35 / 0.55 (UNSOURCED). Measured FastF1 ratios
    apply only when ``ARIS_USE_MEASURED_SC_PIT_LOSS`` is an explicit opt-in
    and ``results/t2b/sc_vsc_pit_loss.json`` is readable; otherwise this
    returns the napkin. Missing file with the flag on also falls back.
    """
    if not track_status_is_sc_vsc(status):
        return None
    s = str(status)
    kind = "sc" if "4" in s else "vsc"
    napkin = SC_PIT_LOSS_MULT if kind == "sc" else VSC_PIT_LOSS_MULT
    try:
        from aris.eval.sc_pit_loss import measured_multiplier

        measured = measured_multiplier(kind, circuit_key)
        if measured is not None:
            return measured
    except Exception:
        pass
    return napkin


class RaceStateOverrides(BaseModel):
    compound: str | None = None
    tyre_life: int | None = None
    fuel_kg: float | None = None
    gap_to_leader_s: float | None = None
    gap_ahead_s: float | None = None
    gap_behind_s: float | None = None
    position: int | None = None
    pit_compound: str | None = None


class RaceState(BaseModel):
    session_id: int
    driver_id: int
    driver_code: str
    driver_name: str
    team: str | None = None
    year: int
    round_no: int
    country: str
    lap_number: int
    compound: str
    tyre_life: int
    fuel_kg: float
    laps_remaining: int
    total_laps: int = DEFAULT_TOTAL_LAPS
    track_name: str = DEFAULT_TRACK_NAME
    gap_to_leader_s: float | None = None
    gap_ahead_s: float | None = None
    gap_behind_s: float | None = None
    position: int | None = None
    undercut_threat: bool = False
    pit_compound: str = "HARD"
    lag1_pace: float | None = None
    lag2_pace: float | None = None
    stint_roll3: float | None = None
    air_temp_c: float | None = None
    track_temp_c: float | None = None
    track_status: str | None = None
    # True when the current lap or the 1–2 prior laps feeding lag1/lag2 pace
    # ran under SC/VSC — recommendations should surface a confidence caveat.
    recent_sc_pace: bool = False
    confidence_caveat: str | None = None
    lap_note: str | None = None
    gap_ahead_history: list[float] = []
    rainfall_mm_per_lap: float | None = None
    weather_rainfall: bool | None = None
    # Per-lap FastF1 weather_data['Rainfall'] (boolean). Session-level
    # session_weather.rainfall (any-sample) stays on weather_rainfall for
    # walk-forward exclusion; it is not a live rain signal.
    rainfall: bool = False

    def with_overrides(self, overrides: RaceStateOverrides) -> RaceState:
        data = self.model_dump()
        for key, val in overrides.model_dump(exclude_none=True).items():
            data[key] = val
        return RaceState(**data)


def _gap_ahead_history(
    session_id: int, driver_id: int, lap_number: int, *, n: int = 5
) -> list[float]:
    """Last ``n`` completed-lap gaps ahead for the focus driver (causal)."""
    try:
        from aris.field.standings import compute_standings

        all_laps = db.fetch_all_laps(session_id)
    except Exception:
        return []
    if all_laps.empty:
        return []
    out: list[float] = []
    start = max(1, int(lap_number) - n + 1)
    for lap in range(start, int(lap_number) + 1):
        rows = compute_standings(all_laps, lap_number=lap, sector_idx=3)
        mine = next((r for r in rows if int(r.driver_id) == int(driver_id)), None)
        if mine is not None and mine.gap_ahead_s is not None:
            out.append(float(mine.gap_ahead_s))
    return out


def _elapsed_s_at_lap(laps: pd.DataFrame, lap_number: int) -> float | None:
    """Cumulative completed lap time before ``lap_number`` (session-relative)."""
    if laps.empty or "lap_time_s" not in laps.columns:
        return None
    prior = laps[laps["lap_number"] < int(lap_number)].sort_values("lap_number")
    times = prior["lap_time_s"].dropna()
    if times.empty:
        return None
    return float(times.sum())


def _lap_rainfall(session_id: int, laps: pd.DataFrame, lap, lap_number: int) -> bool:
    """Per-lap rain from laps.rainfall, else nearest weather_samples row."""
    if "rainfall" in getattr(lap, "index", []) and pd.notna(lap.get("rainfall")):
        return bool(lap.get("rainfall"))
    samples = db.fetch_weather_samples(session_id)
    if not samples:
        return False
    elapsed = _elapsed_s_at_lap(laps, lap_number)
    if elapsed is None:
        return False
    best = min(samples, key=lambda s: abs(float(s["time_s"]) - elapsed))
    return bool(best["rainfall"])


def _pace_lags(
    laps: pd.DataFrame, lap_number: int
) -> tuple[float | None, float | None, float | None]:
    prior = laps[laps["lap_number"] < lap_number].sort_values("lap_number")
    times = prior["lap_time_s"].dropna().tolist()
    if not times:
        return None, None, None
    lag1 = times[-1]
    lag2 = times[-2] if len(times) >= 2 else lag1
    roll3 = sum(times[-3:]) / min(3, len(times[-3:]))
    return float(lag1), float(lag2), float(roll3)


def _recent_sc_pace(laps: pd.DataFrame, lap_number: int, current_status: str | None) -> bool:
    """SC/VSC on the current lap or the 1–2 prior laps that feed lag pace."""
    if track_status_is_sc_vsc(current_status):
        return True
    if "track_status" not in laps.columns:
        return False
    prior = laps[laps["lap_number"] < lap_number].sort_values("lap_number")
    if prior.empty:
        return False
    recent = prior.tail(2)
    for status in recent["track_status"].tolist():
        if track_status_is_sc_vsc(None if pd.isna(status) else str(status)):
            return True
    return False


def build_race_state(
    session_id: int,
    driver_id: int,
    lap_number: int,
    *,
    overrides: RaceStateOverrides | None = None,
    total_laps: int | None = None,
    field_gaps: dict | None = None,
) -> RaceState:
    with db.engine().connect() as conn:
        sess = conn.execute(
            text("SELECT year, round_no, country FROM sessions WHERE session_id = :sid"),
            {"sid": session_id},
        ).one()
        drv = conn.execute(
            text("SELECT code, full_name, team FROM drivers WHERE driver_id = :did"),
            {"did": driver_id},
        ).one()

    track_cfg = load_track_config(
        str(sess.country), year=int(sess.year), round_no=int(sess.round_no)
    )
    if total_laps is None:
        total_laps = track_cfg.total_laps

    laps = db.fetch_laps(session_id, driver_id)
    if laps.empty:
        raise ValueError(f"no laps for session={session_id} driver={driver_id}")

    requested = int(lap_number)
    row = laps[laps["lap_number"] == requested]
    lap_note: str | None = None
    if row.empty:
        max_lap = int(laps["lap_number"].max())
        if requested > max_lap:
            lap_note = f"Lap {requested} not yet available — using lap {max_lap}"
            _log.warning(lap_note)
            requested = max_lap
            row = laps[laps["lap_number"] == requested]
        if row.empty:
            # Nearest lower lap (missing exact row, e.g. in-lap gap).
            prior = laps[laps["lap_number"] < int(lap_number)].sort_values("lap_number")
            if prior.empty:
                requested = int(laps["lap_number"].min())
                row = laps[laps["lap_number"] == requested]
                lap_note = lap_note or f"Lap {lap_number} not found — using lap {requested}"
            else:
                requested = int(prior.iloc[-1]["lap_number"])
                row = laps[laps["lap_number"] == requested]
                lap_note = lap_note or f"Lap {lap_number} not found — using lap {requested}"
        if row.empty:
            raise ValueError(f"lap {lap_number} not found for driver {driver_id}")

    lap = row.iloc[0]
    if requested == 1 or laps[laps["lap_number"] < requested].empty:
        _log.warning("no prior laps for driver=%s lap=%s — lags will be null", driver_id, requested)
    compound = str(lap.get("compound") or "MEDIUM")
    tyre_life = int(lap.get("tyre_life") or 1)
    fuel = estimate_fuel_kg(requested, total_laps=total_laps)
    lag1, lag2, roll3 = _pace_lags(laps, requested)
    weather = db.fetch_session_weather(session_id) or {}
    track_status = str(lap["track_status"]) if pd.notna(lap.get("track_status")) else None
    sc_pace = _recent_sc_pace(laps, requested, track_status)

    gaps = field_gaps or {}
    gap_ahead = gaps.get("gap_ahead_s")
    undercut = gap_ahead is not None and 0 < gap_ahead < 22.0

    state = RaceState(
        session_id=session_id,
        driver_id=driver_id,
        driver_code=str(drv.code),
        driver_name=str(drv.full_name),
        team=str(drv.team) if drv.team else None,
        year=int(sess.year),
        round_no=int(sess.round_no),
        country=str(sess.country),
        lap_number=requested,
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=fuel,
        laps_remaining=max(0, total_laps - requested),
        total_laps=total_laps,
        track_name=track_cfg.name,
        pit_compound="HARD",
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=roll3,
        gap_to_leader_s=gaps.get("gap_to_leader_s"),
        gap_ahead_s=gap_ahead,
        gap_behind_s=gaps.get("gap_behind_s"),
        position=gaps.get("position"),
        undercut_threat=undercut,
        air_temp_c=weather.get("air_temp_c"),
        track_temp_c=weather.get("track_temp_c"),
        track_status=track_status,
        recent_sc_pace=sc_pace,
        confidence_caveat=SC_PACE_CAVEAT if sc_pace else None,
        lap_note=lap_note,
        gap_ahead_history=_gap_ahead_history(session_id, driver_id, requested),
        weather_rainfall=bool(weather["rainfall"]) if weather.get("rainfall") is not None else None,
        rainfall_mm_per_lap=None,
        rainfall=_lap_rainfall(session_id, laps, lap, requested),
    )
    if overrides:
        state = state.with_overrides(overrides)
    return state


def state_to_feature_dict(state: RaceState) -> dict[str, Any]:
    return {
        "compound": state.compound,
        "tyre_life": state.tyre_life,
        "fuel_kg": state.fuel_kg,
        "pit_lap": False,
        "lag1_pace": state.lag1_pace,
        "lag2_pace": state.lag2_pace,
        "stint_roll3": state.stint_roll3,
    }
