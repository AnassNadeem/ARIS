"""Race state snapshot for strategy simulation."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel
from sqlalchemy import text

from aris.io import db
from aris.models.features import estimate_fuel_kg

DEFAULT_TOTAL_LAPS = 57
DEFAULT_TRACK_NAME = "Bahrain"


class RaceStateOverrides(BaseModel):
    compound: str | None = None
    tyre_life: int | None = None
    fuel_kg: float | None = None
    gap_to_leader_s: float | None = None
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
    pit_compound: str = "HARD"
    lag1_pace: float | None = None
    lag2_pace: float | None = None
    stint_roll3: float | None = None

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


def build_race_state(
    session_id: int,
    driver_id: int,
    lap_number: int,
    *,
    overrides: RaceStateOverrides | None = None,
    total_laps: int = DEFAULT_TOTAL_LAPS,
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

    laps = db.fetch_laps(session_id, driver_id)
    if laps.empty:
        raise ValueError(f"no laps for session={session_id} driver={driver_id}")

    row = laps[laps["lap_number"] == lap_number]
    if row.empty:
        raise ValueError(f"lap {lap_number} not found for driver {driver_id}")

    lap = row.iloc[0]
    compound = str(lap.get("compound") or "MEDIUM")
    tyre_life = int(lap.get("tyre_life") or 1)
    fuel = estimate_fuel_kg(int(lap_number), total_laps=total_laps)
    lag1, lag2, roll3 = _pace_lags(laps, lap_number)

    state = RaceState(
        session_id=session_id,
        driver_id=driver_id,
        driver_code=str(drv.code),
        driver_name=str(drv.full_name),
        team=str(drv.team) if drv.team else None,
        year=int(sess.year),
        round_no=int(sess.round_no),
        country=str(sess.country),
        lap_number=int(lap_number),
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=fuel,
        laps_remaining=max(0, total_laps - int(lap_number)),
        total_laps=total_laps,
        pit_compound="HARD",
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=roll3,
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
