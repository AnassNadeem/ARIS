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


def track_status_is_sc_vsc(status: str | None) -> bool:
    """True when a FastF1 TrackStatus string indicates SC / VSC involvement."""
    if status is None:
        return False
    s = str(status).strip()
    if not s or s in ("1", "None", "nan"):
        return False
    return any(code in s for code in _SC_VSC_CODES)


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

    def with_overrides(self, overrides: RaceStateOverrides) -> RaceState:
        data = self.model_dump()
        for key, val in overrides.model_dump(exclude_none=True).items():
            data[key] = val
        return RaceState(**data)


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
