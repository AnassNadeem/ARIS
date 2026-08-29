"""Session parsing and FastF1/backend lap loading for T12 charts.

Tests inject a bundle via ``set_bundle_override`` so they never hit FastF1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

DEFAULT_SESSION_ID = "2025-15-R"

_BundleLoader = Callable[..., "ExplainBundle"]
_OVERRIDE: ExplainBundle | _BundleLoader | None = None


@dataclass
class ExplainBundle:
    """One race session's laps (FastF1-shaped) plus optional weather/messages."""

    year: int
    round_number: int
    session_type: str
    circuit: str
    total_laps: int
    laps: pd.DataFrame
    weather: pd.DataFrame | None = None
    messages: pd.DataFrame | None = None
    session_id: str = DEFAULT_SESSION_ID
    extra: dict[str, Any] = field(default_factory=dict)


def parse_session_id(
    session_id: str | None = None,
    *,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
) -> tuple[int, int, str]:
    """Parse ``2025-15-R`` (or year/round kwargs) into (year, round, session_type)."""
    stype = (session_type or "R").upper()
    if session_id:
        raw = str(session_id).strip()
        token = raw
        for suffix in ("-R", "-S", "-Q"):
            if token.upper().endswith(suffix):
                stype = suffix[1:].upper()
                token = token[: -len(suffix)]
                break
        parts = token.replace("R", "").replace("S", "").split("-")
        if parts and parts[0].isdigit() and len(parts[0]) == 4:
            year = year or int(parts[0])
        if len(parts) > 1 and parts[1].isdigit():
            round_number = round_number or int(parts[1])
    if year is None:
        year = 2025
    if round_number is None:
        round_number = 15
    return int(year), int(round_number), stype


def format_session_id(year: int, round_number: int, session_type: str = "R") -> str:
    return f"{int(year)}-{int(round_number)}-{str(session_type).upper()}"


def set_bundle_override(bundle: ExplainBundle | _BundleLoader | None) -> None:
    """Test hook: skip FastF1 and return this bundle from ``load_explain_bundle``."""
    global _OVERRIDE
    _OVERRIDE = bundle


def load_explain_bundle(
    session_id: str | None = None,
    *,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
) -> ExplainBundle:
    """Load laps/weather/messages for a race. Override wins; else backend FastF1."""
    if _OVERRIDE is not None:
        if callable(_OVERRIDE):
            return _OVERRIDE(
                session_id=session_id,
                year=year,
                round_number=round_number,
                session_type=session_type,
            )
        return _OVERRIDE

    y, rnd, stype = parse_session_id(
        session_id, year=year, round_number=round_number, session_type=session_type
    )
    sid = format_session_id(y, rnd, stype)
    circuit = "Netherlands"
    total_laps = 72
    try:
        from aris.tracks import load_track_config
        from backend.calendar import peek_round_meta

        country, circuit_key = peek_round_meta(y, rnd)
        circuit = str(circuit_key or country or circuit)
        cfg = load_track_config(country or circuit, year=y, round_no=rnd)
        total_laps = int(cfg.total_laps)
        if cfg.country:
            circuit = cfg.country
    except Exception:
        pass

    laps = _load_laps_df(y, rnd, stype)
    weather = _load_weather_df(y, rnd, stype)
    messages = _load_messages_df(y, rnd, stype)
    if not laps.empty and "LapNumber" in laps.columns:
        try:
            total_laps = max(total_laps, int(laps["LapNumber"].max()))
        except (TypeError, ValueError):
            pass
    return ExplainBundle(
        year=y,
        round_number=rnd,
        session_type=stype,
        circuit=circuit,
        total_laps=total_laps,
        laps=laps,
        weather=weather,
        messages=messages,
        session_id=sid,
    )


def _load_laps_df(year: int, round_number: int, session_type: str) -> pd.DataFrame:
    try:
        from backend.sessions import session_laps

        resp = session_laps(year, round_number, session_type)
        return laps_response_to_frame(resp)
    except Exception:
        pass
    try:
        from aris.io.fastf1_session import load_race_session
        from backend.calendar import get_round

        rnd = get_round(year, round_number)
        gp = rnd.name or rnd.official_event_name or "Netherlands"
        sess = load_race_session(year, gp, laps=True, weather=False, messages=False, round_no=round_number)
        return sess.laps.copy()
    except Exception:
        return pd.DataFrame()


def _load_weather_df(year: int, round_number: int, session_type: str) -> pd.DataFrame | None:
    try:
        from backend.sessions import session_weather

        w = session_weather(year, round_number, session_type)
        if not w.timestamp:
            return None
        return pd.DataFrame(
            {
                "timestamp": w.timestamp,
                "Rainfall": w.rainfall,
                "AirTemp": w.air_temp,
                "TrackTemp": w.track_temp,
            }
        )
    except Exception:
        return None


def _load_messages_df(year: int, round_number: int, session_type: str) -> pd.DataFrame | None:
    try:
        from backend.sessions import session_messages

        msgs = session_messages(year, round_number, session_type).messages
        if not msgs:
            return None
        return pd.DataFrame(
            [
                {
                    "Lap": m.lap,
                    "Flag": m.flag,
                    "Category": m.category,
                    "Message": m.message,
                }
                for m in msgs
            ]
        )
    except Exception:
        return None


def laps_response_to_frame(resp: Any) -> pd.DataFrame:
    """Convert ``backend.models.LapsResponse`` into a FastF1-shaped laps frame."""
    rows: list[dict[str, Any]] = []
    stint_by_driver: dict[str, int] = {}
    prev_comp: dict[str, str | None] = {}
    for lap in getattr(resp, "laps", []) or []:
        code = str(lap.driver_code)
        pit_out = bool(lap.pit_out_lap)
        compound = lap.compound
        if code not in stint_by_driver:
            stint_by_driver[code] = 1
        elif pit_out or (
            compound and prev_comp.get(code) and compound != prev_comp.get(code)
        ):
            stint_by_driver[code] += 1
        prev_comp[code] = compound or prev_comp.get(code)
        ms = lap.lap_time_ms
        lap_s = None if ms is None else ms / 1000.0
        rows.append(
            {
                "Driver": code,
                "LapNumber": int(lap.lap_number),
                "LapTimeS": lap_s,
                "LapTime": pd.Timedelta(seconds=lap_s) if lap_s is not None else pd.NaT,
                "Compound": compound,
                "TyreLife": lap.tyre_life,
                "Stint": stint_by_driver[code],
                "PitInTime": 1.0 if lap.pit_in_lap else None,
                "PitOutTime": 1.0 if lap.pit_out_lap else None,
                "TrackStatus": lap.track_status or "1",
                "Position": None,
                "Team": lap.team,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return detect_stints_inplace(df)


def detect_stints_inplace(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure Stint / StintId / LapTimeS exist (FastF1 or synthetic frames)."""
    out = df.copy()
    if "LapTimeS" not in out.columns:
        if "LapTime" in out.columns:
            out["LapTimeS"] = out["LapTime"].map(_td_seconds)
        else:
            out["LapTimeS"] = pd.NA
    if "Stint" in out.columns and out["Stint"].notna().any():
        out["StintId"] = out["Stint"]
        return out
    from aris.physics.stint import detect_stints

    return detect_stints(out)


def _td_seconds(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def driver_laps(bundle: ExplainBundle | pd.DataFrame, driver: str) -> pd.DataFrame:
    laps = bundle.laps if isinstance(bundle, ExplainBundle) else bundle
    if laps is None or laps.empty or "Driver" not in laps.columns:
        return laps if laps is not None else pd.DataFrame()
    code = str(driver).upper()
    out = laps[laps["Driver"].astype(str).str.upper() == code].copy()
    return out.sort_values("LapNumber") if "LapNumber" in out.columns else out
