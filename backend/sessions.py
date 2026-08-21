"""FastF1 session loading: laps, summary, stints, telemetry, weather, results, messages."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from backend.cache import enable_fastf1_cache
from backend.models import (
    CircuitCorner,
    CircuitMapBounds,
    CircuitMapResponse,
    CircuitMarker,
    CircuitPathXY,
    CircuitPathPoint,
    CircuitPathResponse,
    CommentaryEvent,
    DriverFastest,
    LapRow,
    LapsResponse,
    LiveTimingResponse,
    MessagesResponse,
    RaceControlMessage,
    SectorRecord,
    SessionCarPosition,
    SessionEventsResponse,
    SessionPositionsAllResponse,
    SessionPositionsResponse,
    SessionResultRow,
    SessionResultsResponse,
    SessionSummary,
    StintRow,
    StintsResponse,
    TelemetryResponse,
    WeatherSeries,
    WeatherSummary,
)

_log = logging.getLogger(__name__)

_SESSION_CACHE: dict[tuple[int, int, str], Any] = {}


def _td_ms(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "total_seconds"):
        return int(value.total_seconds() * 1000)
    try:
        return int(float(value) * 1000)
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def _bool(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    try:
        if pd.isna(value):
            return False
    except TypeError:
        pass
    return bool(value)


def _get_fastf1_session(year: int, round_number: int, session_type: str):
    """Load by FastF1 round number; fall back to event name if numbering drifts."""
    enable_fastf1_cache()
    import fastf1

    stype = session_type.upper()
    try:
        return fastf1.get_session(year, round_number, stype)
    except Exception as first:
        try:
            from backend.calendar import get_round

            rnd = get_round(year, round_number)
            ident = rnd.official_event_name or rnd.name
            return fastf1.get_session(year, ident, stype)
        except Exception:
            raise first from None


def load_session(year: int, round_number: int, session_type: str, *, telemetry: bool = False, weather: bool = True, messages: bool = False):
    key = (year, round_number, session_type.upper(), telemetry, weather, messages)
    hit = _SESSION_CACHE.get(key)
    if hit is not None:
        return hit
    sess = _get_fastf1_session(year, round_number, session_type)
    sess.load(laps=True, telemetry=telemetry, weather=weather, messages=messages)
    _SESSION_CACHE[key] = sess
    return sess


def _sector_colours(laps: pd.DataFrame) -> dict[tuple[str, int], tuple[str, str, str]]:
    """(driver, lap) -> (s1, s2, s3) colour."""
    colours: dict[tuple[str, int], tuple[str, str, str]] = {}
    if laps.empty:
        return colours
    best_s: dict[str, float] = {}
    for col in ("Sector1Time", "Sector2Time", "Sector3Time"):
        series = laps[col].dropna()
        if series.empty:
            continue
        secs = series.map(lambda x: x.total_seconds() if hasattr(x, "total_seconds") else float(x))
        best_s[col] = float(secs.min())
    personal: dict[str, dict[str, float]] = {}
    prev: dict[str, dict[str, float]] = {}
    ordered = laps.sort_values(["Driver", "LapNumber"])
    for rec in ordered.itertuples(index=False):
        code = str(rec.Driver)
        lap_no = int(rec.LapNumber) if pd.notna(rec.LapNumber) else 0
        tones: list[str] = []
        for col, attr in (
            ("Sector1Time", "Sector1Time"),
            ("Sector2Time", "Sector2Time"),
            ("Sector3Time", "Sector3Time"),
        ):
            val = getattr(rec, attr, None)
            ms = _td_ms(val)
            if ms is None:
                tones.append("grey")
                continue
            sec = ms / 1000.0
            pb = personal.setdefault(code, {})
            last = prev.setdefault(code, {})
            session_best = best_s.get(col)
            if session_best is not None and abs(sec - session_best) < 0.0005:
                tone = "purple"
            elif col not in pb or sec < pb[col]:
                tone = "green"
            elif col in last and sec < last[col]:
                tone = "yellow"
            else:
                tone = "grey"
            pb[col] = min(sec, pb.get(col, sec))
            last[col] = sec
            tones.append(tone)
        colours[(code, lap_no)] = (tones[0], tones[1], tones[2])
    return colours


def session_laps(year: int, round_number: int, session_type: str) -> LapsResponse:
    sess = load_session(year, round_number, session_type)
    laps = sess.laps
    colours = _sector_colours(laps)
    rows: list[LapRow] = []
    for rec in laps.itertuples(index=False):
        if pd.isna(rec.LapNumber) or pd.isna(rec.Driver):
            continue
        code = str(rec.Driver)
        lap_no = int(rec.LapNumber)
        s1, s2, s3 = colours.get((code, lap_no), ("grey", "grey", "grey"))
        rows.append(
            LapRow(
                driver_code=code,
                lap_number=lap_no,
                lap_time_ms=_td_ms(rec.LapTime),
                sector1_ms=_td_ms(rec.Sector1Time),
                sector2_ms=_td_ms(rec.Sector2Time),
                sector3_ms=_td_ms(rec.Sector3Time),
                compound=None if pd.isna(rec.Compound) else str(rec.Compound),
                tyre_life=_int(rec.TyreLife),
                is_personal_best=_bool(getattr(rec, "IsPersonalBest", False)),
                pit_in_lap=pd.notna(rec.PitInTime),
                pit_out_lap=pd.notna(rec.PitOutTime),
                track_status=None if pd.isna(rec.TrackStatus) else str(rec.TrackStatus),
                speed_i1=_num(rec.SpeedI1),
                speed_i2=_num(rec.SpeedI2),
                speed_fl=_num(rec.SpeedFL),
                speed_st=_num(rec.SpeedST),
                s1_colour=s1,  # type: ignore[arg-type]
                s2_colour=s2,  # type: ignore[arg-type]
                s3_colour=s3,  # type: ignore[arg-type]
                team=None if pd.isna(getattr(rec, "Team", None)) else str(rec.Team),
            )
        )
    return LapsResponse(year=year, round_number=round_number, session_type=session_type.upper(), laps=rows)


def session_summary(year: int, round_number: int, session_type: str) -> SessionSummary:
    laps_resp = session_laps(year, round_number, session_type)
    sess = load_session(year, round_number, session_type, weather=True)
    fastest: dict[str, DriverFastest] = {}
    s1 = s2 = s3 = None
    top_speed = None
    top_driver = None
    for lap in laps_resp.laps:
        if lap.lap_time_ms is not None:
            prev = fastest.get(lap.driver_code)
            if prev is None or lap.lap_time_ms < prev.lap_time_ms:
                fastest[lap.driver_code] = DriverFastest(
                    driver_code=lap.driver_code,
                    lap_time_ms=lap.lap_time_ms,
                    lap_number=lap.lap_number,
                    compound=lap.compound,
                )
        if lap.sector1_ms is not None and (s1 is None or lap.sector1_ms < s1.time_ms):
            s1 = SectorRecord(driver_code=lap.driver_code, time_ms=lap.sector1_ms)
        if lap.sector2_ms is not None and (s2 is None or lap.sector2_ms < s2.time_ms):
            s2 = SectorRecord(driver_code=lap.driver_code, time_ms=lap.sector2_ms)
        if lap.sector3_ms is not None and (s3 is None or lap.sector3_ms < s3.time_ms):
            s3 = SectorRecord(driver_code=lap.driver_code, time_ms=lap.sector3_ms)
        for spd in (lap.speed_i1, lap.speed_i2, lap.speed_fl, lap.speed_st):
            if spd is not None and (top_speed is None or spd > top_speed):
                top_speed = spd
                top_driver = lap.driver_code
    weather = WeatherSummary()
    wet = False
    try:
        wd = sess.weather_data
        if wd is not None and not wd.empty:
            air = wd["AirTemp"].dropna() if "AirTemp" in wd else pd.Series(dtype=float)
            track = wd["TrackTemp"].dropna() if "TrackTemp" in wd else pd.Series(dtype=float)
            rain = wd["Rainfall"] if "Rainfall" in wd else pd.Series(dtype=bool)
            weather = WeatherSummary(
                avg_air_temp=float(air.mean()) if not air.empty else None,
                min_air_temp=float(air.min()) if not air.empty else None,
                max_air_temp=float(air.max()) if not air.empty else None,
                avg_track_temp=float(track.mean()) if not track.empty else None,
                min_track_temp=float(track.min()) if not track.empty else None,
                max_track_temp=float(track.max()) if not track.empty else None,
                rainfall=bool(rain.any()) if not rain.empty else None,
            )
            wet = bool(weather.rainfall)
    except Exception:
        pass
    return SessionSummary(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        fastest_laps=sorted(fastest.values(), key=lambda x: x.lap_time_ms),
        sector1_record=s1,
        sector2_record=s2,
        sector3_record=s3,
        top_speed_kph=top_speed,
        top_speed_driver=top_driver,
        laps_completed=len(laps_resp.laps),
        weather=weather,
        wet_reduced_confidence=wet,
    )


def session_stints(year: int, round_number: int, session_type: str) -> StintsResponse:
    laps = session_laps(year, round_number, session_type).laps
    grouped: dict[str, list[LapRow]] = {}
    for lap in laps:
        grouped.setdefault(lap.driver_code, []).append(lap)
    stints: list[StintRow] = []
    for code, rows in grouped.items():
        rows = sorted(rows, key=lambda r: r.lap_number)
        current: list[LapRow] = []
        stint_no = 1
        prev_comp = None
        for lap in rows:
            new_stint = bool(lap.pit_out_lap) or (prev_comp is not None and lap.compound != prev_comp and lap.compound)
            if current and new_stint:
                stints.append(_stint_from_laps(code, stint_no, current))
                stint_no += 1
                current = [lap]
            else:
                current.append(lap)
            prev_comp = lap.compound or prev_comp
        if current:
            stints.append(_stint_from_laps(code, stint_no, current))
    return StintsResponse(year=year, round_number=round_number, session_type=session_type.upper(), stints=stints)


def _stint_from_laps(code: str, stint_no: int, rows: list[LapRow]) -> StintRow:
    times = [r.lap_time_ms for r in rows if r.lap_time_ms and not r.pit_in_lap and not r.pit_out_lap]
    avg = sum(times) / len(times) if times else None
    deg = None
    if len(times) >= 4:
        n = len(times)
        xs = list(range(n))
        xbar = sum(xs) / n
        ybar = sum(times) / n
        num = sum((x - xbar) * (y - ybar) for x, y in zip(xs, times))
        den = sum((x - xbar) ** 2 for x in xs) or 1
        deg = num / den
    fresh = rows[0].tyre_life == 1 if rows[0].tyre_life is not None else None
    return StintRow(
        driver_code=code,
        stint_number=stint_no,
        compound=rows[0].compound,
        fresh_tyre=fresh,
        lap_start=rows[0].lap_number,
        lap_end=rows[-1].lap_number,
        total_laps=rows[-1].lap_number - rows[0].lap_number + 1,
        average_lap_ms=avg,
        deg_rate_ms_per_lap=deg,
    )


def session_telemetry(
    year: int, round_number: int, session_type: str, driver_code: str, *, full: bool = False
) -> TelemetryResponse:
    sess = load_session(year, round_number, session_type, telemetry=True)
    laps = sess.laps.pick_drivers(driver_code.upper())
    if laps.empty:
        raise KeyError(f"No laps for {driver_code}")
    fast = laps.pick_fastest()
    car = fast.get_car_data().add_distance()
    try:
        pos = fast.get_pos_data()
    except Exception:
        pos = None
    step = 1 if full else 10
    dist = car["Distance"].tolist()[::step] if "Distance" in car else []
    speed = car["Speed"].tolist()[::step] if "Speed" in car else []
    throttle = car["Throttle"].tolist()[::step] if "Throttle" in car else []
    brake = [float(b) * 100 if float(b) <= 1 else float(b) for b in (car["Brake"].tolist()[::step] if "Brake" in car else [])]
    drs = [int(x) for x in (car["DRS"].tolist()[::step] if "DRS" in car else [])]
    rpm = [float(x) for x in (car["RPM"].tolist()[::step] if "RPM" in car else [])]
    gear = [int(x) if pd.notna(x) else 0 for x in (car["nGear"].tolist()[::step] if "nGear" in car else [])]
    xs: list[float] = []
    ys: list[float] = []
    if pos is not None and not pos.empty and "X" in pos.columns:
        xs = [float(x) for x in pos["X"].tolist()[::step]]
        ys = [float(y) for y in pos["Y"].tolist()[::step]]
    n = len(dist)
    return TelemetryResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        driver_code=driver_code.upper(),
        sampled=not full,
        distance=[float(x) for x in dist[:n]],
        speed=[float(x) for x in speed[:n]],
        throttle=[float(x) for x in throttle[:n]],
        brake=brake[:n],
        drs=drs[:n],
        rpm=rpm[:n],
        gear=gear[:n],
        x=xs[:n] if xs else [],
        y=ys[:n] if ys else [],
    )


def session_weather(year: int, round_number: int, session_type: str) -> WeatherSeries:
    sess = load_session(year, round_number, session_type, weather=True)
    wd = sess.weather_data
    empty = WeatherSeries(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        timestamp=[],
        air_temp=[],
        track_temp=[],
        humidity=[],
        rainfall=[],
        wind_speed=[],
        wind_direction=[],
    )
    if wd is None or wd.empty:
        return empty
    ts = []
    for t in wd.index:
        if hasattr(t, "isoformat"):
            ts.append(t.isoformat())
        else:
            ts.append(str(t))
    rain_col = wd["Rainfall"] if "Rainfall" in wd else None
    rainfall = []
    if rain_col is not None:
        for v in rain_col.tolist():
            rainfall.append(None if pd.isna(v) else bool(v))
    return WeatherSeries(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        timestamp=ts,
        air_temp=[_num(v) for v in wd["AirTemp"].tolist()] if "AirTemp" in wd else [],
        track_temp=[_num(v) for v in wd["TrackTemp"].tolist()] if "TrackTemp" in wd else [],
        humidity=[_num(v) for v in wd["Humidity"].tolist()] if "Humidity" in wd else [],
        rainfall=rainfall,
        wind_speed=[_num(v) for v in wd["WindSpeed"].tolist()] if "WindSpeed" in wd else [],
        wind_direction=[_num(v) for v in wd["WindDirection"].tolist()] if "WindDirection" in wd else [],
    )


def session_results(year: int, round_number: int, session_type: str) -> SessionResultsResponse:
    sess = load_session(year, round_number, session_type)
    results = sess.results
    rows: list[SessionResultRow] = []
    winner_ms = None
    if results is not None and not results.empty:
        ordered = results.sort_values("Position")
        for rec in ordered.itertuples(index=False):
            pos = _int(rec.Position)
            time_ms = _td_ms(getattr(rec, "Time", None))
            if pos == 1 and time_ms:
                winner_ms = time_ms
            status = str(getattr(rec, "Status", "") or "Finished")
            gap = None
            if winner_ms is not None and time_ms is not None and pos != 1:
                gap = time_ms - winner_ms
            fl = False
            try:
                fl = bool(getattr(rec, "FastestLapRank", None) == 1)
            except Exception:
                fl = False
            rows.append(
                SessionResultRow(
                    position=pos,
                    driver_code=str(rec.Abbreviation),
                    team=None if pd.isna(rec.TeamName) else str(rec.TeamName),
                    time_ms=time_ms,
                    gap_to_winner_ms=gap,
                    points=_num(getattr(rec, "Points", None)),
                    fastest_lap=fl,
                    laps_completed=_int(getattr(rec, "Laps", None)),
                    status=status,
                    grid=_int(getattr(rec, "GridPosition", None)),
                )
            )
    return SessionResultsResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        results=rows,
    )


def session_messages(year: int, round_number: int, session_type: str) -> MessagesResponse:
    sess = load_session(year, round_number, session_type, messages=True)
    msgs: list[RaceControlMessage] = []
    raw = getattr(sess, "messages", None)
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return MessagesResponse(
            year=year, round_number=round_number, session_type=session_type.upper(), messages=[]
        )
    for rec in raw.itertuples(index=False):
        t = getattr(rec, "Time", None) or getattr(rec, "Utc", None)
        utc = None
        if hasattr(t, "isoformat"):
            utc = t.isoformat()
        elif t is not None:
            utc = str(t)
        msgs.append(
            RaceControlMessage(
                utc_time=utc,
                lap=_int(getattr(rec, "Lap", None)),
                flag=None if pd.isna(getattr(rec, "Flag", None)) else str(rec.Flag),
                category=None if pd.isna(getattr(rec, "Category", None)) else str(rec.Category),
                message=str(getattr(rec, "Message", "") or ""),
            )
        )
    return MessagesResponse(
        year=year, round_number=round_number, session_type=session_type.upper(), messages=msgs
    )


def _normalize_xy(xs: list[float], ys: list[float], w: float = 440, h: float = 280, pad: float = 20) -> list[CircuitPathPoint]:
    if not xs or not ys:
        return []
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    dx = max(maxx - minx, 1e-6)
    dy = max(maxy - miny, 1e-6)
    scale = min((w - 2 * pad) / dx, (h - 2 * pad) / dy)
    points: list[CircuitPathPoint] = []
    for x, y in zip(xs, ys):
        px = pad + (x - minx) * scale
        py = h - pad - (y - miny) * scale
        points.append(CircuitPathPoint(x=round(px, 2), y=round(py, 2)))
    return points


def circuit_path(year: int, round_number: int, session_type: str = "R") -> CircuitPathResponse:
    try:
        sess = load_session(year, round_number, session_type, telemetry=True)
        laps = sess.laps
        fast = laps.pick_fastest()
        pos = fast.get_pos_data()
        xs = [float(x) for x in pos["X"].tolist()] if pos is not None and "X" in pos else []
        ys = [float(y) for y in pos["Y"].tolist()] if pos is not None and "Y" in pos else []
        # downsample path
        step = max(1, len(xs) // 400)
        xs, ys = xs[::step], ys[::step]
        points = _normalize_xy(xs, ys)
        corners: list[CircuitPathPoint] = []
        try:
            info = sess.get_circuit_info()
            if info is not None and getattr(info, "corners", None) is not None:
                c = info.corners
                if "X" in c.columns:
                    corners = _normalize_xy(
                        [float(x) for x in c["X"].tolist()],
                        [float(y) for y in c["Y"].tolist()],
                    )
        except Exception:
            corners = []
        return CircuitPathResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            points=points,
            estimated=not bool(points),
            corners=corners,
        )
    except Exception:
        return CircuitPathResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            points=[],
            estimated=True,
        )


def replay_timing(year: int, round_number: int, session_type: str, current_lap: int) -> LiveTimingResponse:
    from backend.models import LiveTimingResponse, LiveTimingRow
    from backend.standings import team_colour

    raw = timing_at_lap(year, round_number, session_type, current_lap)
    rows = [
        LiveTimingRow(
            position=int(r["position"]),
            driver_code=str(r["driver_code"]),
            gap_to_leader_s=r.get("gap_to_leader_s"),
            last_lap_ms=r.get("last_lap_ms"),
            best_lap_ms=r.get("best_lap_ms"),
            sector1_ms=r.get("sector1_ms"),
            sector2_ms=r.get("sector2_ms"),
            sector3_ms=r.get("sector3_ms"),
            s1_colour=r.get("s1_colour") or "grey",
            s2_colour=r.get("s2_colour") or "grey",
            s3_colour=r.get("s3_colour") or "grey",
            compound=_compound_letter(r.get("compound")),
            tyre_life=r.get("tyre_life"),
            team_colour=team_colour(str(r.get("team") or "")),
        )
        for r in raw
    ]
    return LiveTimingResponse(
        is_live=False, rows=rows, current_lap=current_lap, replay=True
    )


def _compound_letter(raw: str | None) -> str | None:
    if not raw:
        return None
    u = str(raw).upper()
    if u.startswith("SOFT") or u == "S":
        return "S"
    if u.startswith("MED") or u == "M":
        return "M"
    if u.startswith("HARD") or u == "H":
        return "H"
    if u.startswith("INTER") or u == "I":
        return "I"
    if u.startswith("WET") or u == "W":
        return "W"
    return u[:1]


def timing_at_lap(year: int, round_number: int, session_type: str, current_lap: int) -> list[dict[str, Any]]:
    """Replay timing tower derived from completed laps up to current_lap."""
    from backend.analytics import gap_history, position_history

    laps = session_laps(year, round_number, session_type).laps
    pos = position_history(year, round_number)
    gaps = gap_history(year, round_number)
    pos_map: dict[str, int] = {}
    gap_map: dict[str, float] = {}
    for row in pos.laps:
        if row.lap <= current_lap:
            pos_map = row.positions
    for row in gaps.laps:
        if row.lap <= current_lap:
            gap_map = row.gaps
    latest: dict[str, LapRow] = {}
    best: dict[str, int] = {}
    for lap in laps:
        if lap.lap_number > current_lap:
            continue
        latest[lap.driver_code] = lap
        if lap.lap_time_ms is not None:
            if lap.driver_code not in best or lap.lap_time_ms < best[lap.driver_code]:
                best[lap.driver_code] = lap.lap_time_ms
    rows = []
    for code, lap in latest.items():
        rows.append(
            {
                "position": pos_map.get(code, 99),
                "driver_code": code,
                "gap_to_leader_s": gap_map.get(code),
                "last_lap_ms": lap.lap_time_ms,
                "best_lap_ms": best.get(code),
                "sector1_ms": lap.sector1_ms,
                "sector2_ms": lap.sector2_ms,
                "sector3_ms": lap.sector3_ms,
                "s1_colour": lap.s1_colour,
                "s2_colour": lap.s2_colour,
                "s3_colour": lap.s3_colour,
                "compound": lap.compound,
                "tyre_life": lap.tyre_life,
                "team": lap.team,
            }
        )
    rows.sort(key=lambda r: r["position"])
    return rows


def _bounds_and_norm(
    xs: list[float], ys: list[float], w: float = 400.0, h: float = 240.0, pad: float = 20.0
) -> tuple[CircuitMapBounds | None, list[float], list[float]]:
    if not xs or not ys:
        return None, [], []
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = max(max_x - min_x, 1e-6)
    dy = max(max_y - min_y, 1e-6)
    nx: list[float] = []
    ny: list[float] = []
    for x, y in zip(xs, ys):
        nx.append(round(pad + (x - min_x) / dx * w, 2))
        ny.append(round(pad + (1.0 - (y - min_y) / dy) * h, 2))
    return CircuitMapBounds(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y), nx, ny


def _apply_bounds(
    x: float, y: float, bounds: CircuitMapBounds, w: float = 400.0, h: float = 240.0, pad: float = 20.0
) -> tuple[float, float]:
    dx = max(bounds.max_x - bounds.min_x, 1e-6)
    dy = max(bounds.max_y - bounds.min_y, 1e-6)
    return (
        round(pad + (x - bounds.min_x) / dx * w, 2),
        round(pad + (1.0 - (y - bounds.min_y) / dy) * h, 2),
    )


def point_at_path_frac(path_x: list[float], path_y: list[float], frac: float) -> tuple[float, float]:
    n = min(len(path_x), len(path_y))
    if n < 2:
        return 220.0, 140.0
    f = (frac % 1.0 + 1.0) % 1.0
    total = 0.0
    segs: list[tuple[float, float, float, float, float]] = []
    for i in range(n - 1):
        dx = path_x[i + 1] - path_x[i]
        dy = path_y[i + 1] - path_y[i]
        ln = (dx * dx + dy * dy) ** 0.5
        if ln <= 0:
            continue
        segs.append((path_x[i], path_y[i], path_x[i + 1], path_y[i + 1], ln))
        total += ln
    if total <= 0 or not segs:
        return path_x[0], path_y[0]
    target = f * total
    acc = 0.0
    for x0, y0, x1, y1, ln in segs:
        if acc + ln >= target:
            t = (target - acc) / ln if ln else 0.0
            t = max(0.0, min(1.0, t))
            return x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        acc += ln
    return path_x[-1], path_y[-1]


def compute_path_distance(
    car_x: float,
    car_y: float,
    path_x: list[float],
    path_y: list[float],
) -> float:
    """Nearest-point projection of (car_x, car_y) onto the circuit polyline.

    Returns a fraction 0.0–1.0 of total path length.
    """
    import numpy as np

    if len(path_x) < 2 or len(path_y) < 2:
        return 0.0
    n = min(len(path_x), len(path_y))
    path = np.array(list(zip(path_x[:n], path_y[:n])), dtype=float)
    car = np.array([car_x, car_y], dtype=float)
    total_length = 0.0
    segs: list[tuple[np.ndarray, np.ndarray, float]] = []
    for i in range(len(path) - 1):
        a = path[i]
        b = path[i + 1]
        seg_len = float(np.linalg.norm(b - a))
        if seg_len <= 0:
            continue
        segs.append((a, b, seg_len))
        total_length += seg_len
    if total_length <= 0 or not segs:
        return 0.0
    min_dist = float("inf")
    best_frac = 0.0
    cumulative = 0.0
    for a, b, seg_len in segs:
        ab = b - a
        t = float(np.clip(np.dot(car - a, ab) / (seg_len ** 2), 0.0, 1.0))
        proj = a + t * ab
        dist = float(np.linalg.norm(car - proj))
        if dist < min_dist:
            min_dist = dist
            best_frac = (cumulative + t * seg_len) / total_length
        cumulative += seg_len
    return float(best_frac)


def _nearest_index(distances: list[float], target: float) -> int:
    if not distances:
        return 0
    best_i = 0
    best = abs(distances[0] - target)
    for i, d in enumerate(distances):
        err = abs(d - target)
        if err < best:
            best = err
            best_i = i
    return best_i


def circuit_map(year: int, round_number: int, *, _fallback: bool = True) -> CircuitMapResponse:
    """Track outline, corners, DRS and sector markers from FastF1."""
    empty = CircuitMapResponse(
        year=year,
        round_number=round_number,
        available=False,
        fallback=True,
        error="Corner data unavailable for this circuit",
    )

    def _unavailable() -> CircuitMapResponse:
        if _fallback and year == 2026:
            fb = circuit_map(2025, round_number, _fallback=False)
            if fb.available:
                return fb.model_copy(update={"year": year, "round_number": round_number})
        return empty

    try:
        sess = load_session(year, round_number, "R", telemetry=True)
        laps = sess.laps
        if laps is None or laps.empty:
            return _unavailable()
        pos = None
        try:
            fast = laps.pick_fastest()
            pos = fast.get_pos_data()
        except Exception as extra:
            _log.warning("pick_fastest failed for %s R%s: %s", year, round_number, extra)
            pos = None
        if pos is None or getattr(pos, "empty", True) or "X" not in getattr(pos, "columns", []):
            pos_data = getattr(sess, "pos_data", None) or {}
            drivers = list(pos_data.keys())
            if drivers:
                pos = pos_data[drivers[0]]
            else:
                return _unavailable()
        if pos is None or getattr(pos, "empty", True) or "X" not in pos.columns:
            return _unavailable()
        raw_x = [float(v) for v in pos["X"].dropna().tolist()]
        raw_y = [float(v) for v in pos["Y"].dropna().tolist()]
        if not raw_x or not raw_y:
            return _unavailable()
        if max(raw_x) - min(raw_x) == 0 or max(raw_y) - min(raw_y) == 0:
            return _unavailable()
        step = max(1, len(raw_x) // 400)
        raw_x, raw_y = raw_x[::step], raw_y[::step]
        bounds, nx, ny = _bounds_and_norm(raw_x, raw_y)
        if bounds is None or len(nx) < 2:
            return _unavailable()

        npts = max(len(nx) - 1, 1)
        corners: list[CircuitCorner] = []
        markers: list[CircuitMarker] = []
        drs_segments: list[list[int]] = []
        try:
            info = sess.get_circuit_info()
        except Exception as extra:
            _log.warning("get_circuit_info failed for %s R%s: %s", year, round_number, extra)
            info = None
        if info is not None:
            cdf = getattr(info, "corners", None)
            if cdf is not None and not getattr(cdf, "empty", True):
                n = max(len(cdf), 1)
                dist_col = "Distance" if "Distance" in getattr(pos, "columns", []) else None
                pos_dist = [float(v) for v in pos["Distance"].tolist()] if dist_col else []
                for i, rec in cdf.iterrows():
                    number = (
                        int(rec["Number"])
                        if "Number" in cdf.columns and pd.notna(rec.get("Number"))
                        else int(i) + 1
                    )
                    letter = ""
                    if "Letter" in cdf.columns and pd.notna(rec.get("Letter")):
                        letter = str(rec["Letter"])
                    angle = _num(rec.get("Angle")) if "Angle" in cdf.columns else None
                    dist = _num(rec.get("Distance")) if "Distance" in cdf.columns else None
                    if "X" in cdf.columns and "Y" in cdf.columns and pd.notna(rec.get("X")):
                        cx, cy = _apply_bounds(float(rec["X"]), float(rec["Y"]), bounds)
                    elif dist is not None and pos_dist:
                        idx_src = _nearest_index(pos_dist, dist)
                        idx = min(len(nx) - 1, int(idx_src / max(len(pos_dist) - 1, 1) * npts))
                        cx, cy = nx[idx], ny[idx]
                    else:
                        idx = min(len(nx) - 1, int((number - 0.5) / n * npts))
                        cx, cy = nx[idx], ny[idx]
                    corners.append(
                        CircuitCorner(
                            number=number,
                            letter=letter,
                            angle=angle,
                            distance=dist,
                            x=cx,
                            y=cy,
                            description=f"Turn {number}{letter}".strip(),
                        )
                    )
            lights = getattr(info, "marshal_lights", None)
            if lights is not None and not getattr(lights, "empty", True) and "X" in lights.columns:
                idxs: list[int] = []
                for _, rec in lights.iterrows():
                    if pd.isna(rec.get("X")):
                        continue
                    mx, my = _apply_bounds(float(rec["X"]), float(rec["Y"]), bounds)
                    dists = [((mx - x) ** 2 + (my - y) ** 2) ** 0.5 for x, y in zip(nx, ny)]
                    idx = _nearest_index(dists, 0.0)
                    idxs.append(idx)
                    markers.append(CircuitMarker(kind="drs", x=mx, y=my, label="DRS"))
                for a, b in zip(idxs[::2], idxs[1::2]):
                    drs_segments.append([a, b])
            sectors = getattr(info, "marshal_sectors", None)
            if sectors is not None and not getattr(sectors, "empty", True) and "X" in sectors.columns:
                labels = [("S1", "s1"), ("S2", "s2"), ("S3", "s3")]
                count = 0
                for _, rec in sectors.iterrows():
                    if count >= 3 or pd.isna(rec.get("X")):
                        continue
                    mx, my = _apply_bounds(float(rec["X"]), float(rec["Y"]), bounds)
                    lab, kind = labels[count]
                    markers.append(CircuitMarker(kind=kind, x=mx, y=my, label=lab))
                    count += 1

        if not any(m.kind in {"s1", "s2", "s3"} for m in markers) and len(nx) > 3:
            for frac, lab, kind in ((1 / 3, "S1", "s1"), (2 / 3, "S2", "s2"), (0.99, "S3", "s3")):
                idx = min(len(nx) - 1, int(frac * npts))
                markers.append(CircuitMarker(kind=kind, x=nx[idx], y=ny[idx], label=lab))

        return CircuitMapResponse(
            year=year,
            round_number=round_number,
            x=nx,
            y=ny,
            corners=corners,
            markers=markers,
            drs_segments=drs_segments,
            bounds=bounds,
            available=True,
            fallback=False,
        )
    except Exception as extra:
        _log.warning("circuit_map failed for %s R%s: %s", year, round_number, extra)
        if _fallback and year == 2026:
            fb = circuit_map(2025, round_number, _fallback=False)
            if fb.available:
                return fb.model_copy(update={"year": year, "round_number": round_number})
        return empty


def session_positions(
    year: int, round_number: int, session_type: str, lap: int
) -> SessionPositionsResponse:
    from backend.standings import team_colour

    empty = SessionPositionsResponse(
        year=year, round_number=round_number, session_type=session_type.upper(), lap=lap, positions=[]
    )
    try:
        cmap = circuit_map(year, round_number)
        bounds = cmap.bounds
        sess = load_session(year, round_number, session_type, telemetry=True)
        results = sess.results
        laps_df = sess.laps
        if laps_df is None or laps_df.empty:
            return empty

        code_by_num: dict[str, str] = {}
        team_by_code: dict[str, str | None] = {}
        dnf_codes: set[str] = set()
        if results is not None and not results.empty:
            for _, rec in results.iterrows():
                code = str(rec.get("Abbreviation") or rec.get("Driver") or "")[:3].upper()
                num = rec.get("DriverNumber")
                if not code:
                    continue
                if num is not None and pd.notna(num):
                    code_by_num[str(int(num))] = code
                team_by_code[code] = team_colour(str(rec.get("TeamName") or rec.get("Team") or ""))
                status = str(rec.get("Status") or "")
                laps_done = _int(rec.get("Laps")) or 0
                low = status.lower()
                finished = low in {"finished", "lapped"} or "+" in status or "lap" in low and "+" in status
                if not finished and laps_done < max(lap, 1) and low not in {"", "finished"}:
                    dnf_codes.add(code)

        this_lap = laps_df[laps_df["LapNumber"] == lap] if "LapNumber" in laps_df.columns else laps_df.iloc[0:0]
        ref_time = None
        if not this_lap.empty and "Time" in this_lap.columns:
            times = this_lap["Time"].dropna()
            if not times.empty:
                ref_time = times.median()

        positions: list[SessionCarPosition] = []
        pos_data = getattr(sess, "pos_data", None) or {}
        for num, df in pos_data.items():
            code = code_by_num.get(str(num), "")
            if not code:
                try:
                    drv = sess.get_driver(str(num))
                    code = str(getattr(drv, "Abbreviation", "") or "")[:3].upper()
                except Exception:
                    code = f"D{num}"
            if df is None or getattr(df, "empty", True) or "X" not in df.columns:
                continue
            try:
                if ref_time is not None and "Time" in df.columns:
                    delta = (df["Time"] - ref_time).abs()
                    row = df.iloc[int(delta.argmin())]
                else:
                    row = df.iloc[min(len(df) - 1, max(0, int(lap * len(df) / 80)))]
                rx, ry = float(row["X"]), float(row["Y"])
            except Exception:
                continue
            px, py = _apply_bounds(rx, ry, bounds) if bounds else (rx, ry)
            pitted = False
            if "Status" in df.columns:
                pitted = "pit" in str(row.get("Status") or "").lower()
            drv_laps = this_lap[this_lap["Driver"] == code] if "Driver" in this_lap.columns else this_lap.iloc[0:0]
            if not drv_laps.empty:
                for col in ("PitInTime", "PitOutTime"):
                    if col in drv_laps.columns:
                        pit_val = drv_laps.iloc[0].get(col)
                        pitted = pitted or (pit_val is not None and not pd.isna(pit_val))
            positions.append(
                SessionCarPosition(
                    driver_code=code,
                    x=px,
                    y=py,
                    team_colour=team_by_code.get(code),
                    is_pitted=bool(pitted),
                    is_dnf=code in dnf_codes,
                )
            )

        if not positions and "Driver" in laps_df.columns:
            for code in laps_df["Driver"].unique().tolist():
                try:
                    dlaps = laps_df[(laps_df["Driver"] == code) & (laps_df["LapNumber"] == lap)]
                    if dlaps.empty:
                        dlaps = laps_df[laps_df["Driver"] == code].tail(1)
                    if dlaps.empty:
                        continue
                    pdata = dlaps.iloc[0].get_pos_data()
                    if pdata is None or pdata.empty:
                        continue
                    mid = pdata.iloc[len(pdata) // 2]
                    rx, ry = float(mid["X"]), float(mid["Y"])
                    px, py = _apply_bounds(rx, ry, bounds) if bounds else (rx, ry)
                    positions.append(
                        SessionCarPosition(
                            driver_code=str(code),
                            x=px,
                            y=py,
                            team_colour=team_by_code.get(str(code)),
                            is_dnf=str(code) in dnf_codes,
                        )
                    )
                except Exception:
                    continue

        return SessionPositionsResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            lap=lap,
            positions=positions,
        )
    except Exception:
        return empty


def circuit_preview_from_map(full: CircuitMapResponse) -> CircuitMapResponse:
    """Downsample a cached full map to ~20 points for index cards."""
    if not full.x or not full.y or not full.available:
        return CircuitMapResponse(
            year=full.year,
            round_number=full.round_number,
            available=False,
            fallback=True,
            error=full.error or "Circuit preview unavailable",
        )
    step = max(1, len(full.x) // 20)
    xs = full.x[::step]
    ys = full.y[::step]
    if xs[-1] != full.x[-1]:
        xs.append(full.x[-1])
        ys.append(full.y[-1])
    return CircuitMapResponse(
        year=full.year,
        round_number=full.round_number,
        x=xs[:21],
        y=ys[:21],
        corners=[],
        markers=[],
        drs_segments=[],
        bounds=full.bounds,
        available=True,
        fallback=False,
        view_box=full.view_box,
    )


def build_circuit_preview(year: int, round_number: int) -> CircuitMapResponse:
    """20-point Quali outline for the circuits index. Used by startup pre-warm only."""
    empty = CircuitMapResponse(
        year=year,
        round_number=round_number,
        available=False,
        fallback=True,
        error="Circuit preview unavailable",
    )
    try:
        sess = load_session(year, round_number, "Q", telemetry=True, weather=False, messages=False)
        laps = sess.laps
        if laps is None or laps.empty:
            return empty
        fast = laps.pick_fastest()
        pos = fast.get_pos_data()
        if pos is None or getattr(pos, "empty", True) or "X" not in pos.columns:
            return empty
        x = pos["X"].dropna().values
        y = pos["Y"].dropna().values
        if len(x) < 10:
            return empty
        indices = [int(i * (len(x) - 1) / 19) for i in range(20)]
        raw_x = [float(x[i]) for i in indices]
        raw_y = [float(y[i]) for i in indices]
        bounds, nx, ny = _bounds_and_norm(raw_x, raw_y)
        if bounds is None or len(nx) < 2:
            return empty
        return CircuitMapResponse(
            year=year,
            round_number=round_number,
            x=nx,
            y=ny,
            bounds=bounds,
            available=True,
            fallback=False,
        )
    except Exception as extra:
        _log.warning("circuit preview failed for %s R%s: %s", year, round_number, extra)
        return empty


def session_positions_all(
    year: int, round_number: int, session_type: str = "R"
) -> SessionPositionsAllResponse:
    from backend.standings import team_colour

    empty = SessionPositionsAllResponse(
        year=year, round_number=round_number, session_type=session_type.upper(), laps={}
    )
    try:
        cmap = circuit_map(year, round_number)
        bounds = cmap.bounds
        sess = load_session(year, round_number, session_type, telemetry=True)
        laps_df = sess.laps
        results = sess.results
        if laps_df is None or laps_df.empty:
            return empty
        max_lap = int(laps_df["LapNumber"].max()) if "LapNumber" in laps_df.columns else 0
        if max_lap < 1:
            return empty

        code_by_num: dict[str, str] = {}
        team_by_code: dict[str, str | None] = {}
        last_lap_by_code: dict[str, int] = {}
        if results is not None and not results.empty:
            for _, rec in results.iterrows():
                code = str(rec.get("Abbreviation") or rec.get("Driver") or "")[:3].upper()
                num = rec.get("DriverNumber")
                if not code:
                    continue
                if num is not None and pd.notna(num):
                    code_by_num[str(int(num))] = code
                team_by_code[code] = team_colour(str(rec.get("TeamName") or rec.get("Team") or ""))
                last_lap_by_code[code] = _int(rec.get("Laps")) or 0

        if "Driver" in laps_df.columns and "LapNumber" in laps_df.columns:
            for code, grp in laps_df.groupby("Driver"):
                last_lap_by_code[str(code)] = int(grp["LapNumber"].max())

        pos_data = getattr(sess, "pos_data", None) or {}
        laps_out: dict[str, list[SessionCarPosition]] = {str(n): [] for n in range(1, max_lap + 1)}

        for num, df in pos_data.items():
            code = code_by_num.get(str(num), "")
            if not code:
                try:
                    drv = sess.get_driver(str(num))
                    code = str(getattr(drv, "Abbreviation", "") or "")[:3].upper()
                except Exception:
                    code = f"D{num}"
            if df is None or getattr(df, "empty", True) or "X" not in df.columns:
                continue
            drv_laps = (
                laps_df[laps_df["Driver"] == code]
                if "Driver" in laps_df.columns
                else laps_df.iloc[0:0]
            )
            last_for_driver = last_lap_by_code.get(code, max_lap)
            for lap_no in range(1, max_lap + 1):
                row = None
                this = drv_laps[drv_laps["LapNumber"] == lap_no] if not drv_laps.empty else drv_laps
                ref_time = None
                pitted = False
                if not this.empty:
                    for col in ("LapStartTime", "Time"):
                        if col in this.columns and pd.notna(this.iloc[0].get(col)):
                            ref_time = this.iloc[0].get(col)
                            break
                    for col in ("PitInTime", "PitOutTime"):
                        if col in this.columns:
                            pit_val = this.iloc[0].get(col)
                            pitted = pitted or (pit_val is not None and not pd.isna(pit_val))
                try:
                    if ref_time is not None and "Time" in df.columns:
                        delta = (df["Time"] - ref_time).abs()
                        row = df.iloc[int(delta.argmin())]
                    else:
                        frac = lap_no / max(max_lap, 1)
                        row = df.iloc[min(len(df) - 1, max(0, int(frac * (len(df) - 1))))]
                    rx, ry = float(row["X"]), float(row["Y"])
                except Exception:
                    continue
                px, py = _apply_bounds(rx, ry, bounds) if bounds else (rx, ry)
                path_frac = 0.0
                if cmap.x and cmap.y:
                    try:
                        path_frac = compute_path_distance(px, py, cmap.x, cmap.y)
                    except Exception:
                        path_frac = 0.0
                speed_ms = None
                if not this.empty and "LapTime" in this.columns:
                    lt = this.iloc[0].get("LapTime")
                    if lt is not None and pd.notna(lt) and hasattr(lt, "total_seconds"):
                        speed_ms = float(lt.total_seconds())
                laps_out[str(lap_no)].append(
                    SessionCarPosition(
                        driver_code=code,
                        x=px,
                        y=py,
                        team_colour=team_by_code.get(code),
                        is_pitted=bool(pitted),
                        is_dnf=last_for_driver < max_lap and lap_no > last_for_driver,
                        path_frac=path_frac,
                        speed_ms=speed_ms,
                    )
                )

        if cmap.x and cmap.y and not any(laps_out.values()):
            for lap_no in range(1, max_lap + 1):
                field = (
                    laps_df[laps_df["LapNumber"] == lap_no]
                    if "LapNumber" in laps_df.columns
                    else laps_df.iloc[0:0]
                )
                if field.empty:
                    continue
                ordered = field.sort_values("Position") if "Position" in field.columns else field
                for i, rec in ordered.iterrows():
                    code = str(rec.get("Driver") or "")[:3].upper()
                    if not code:
                        continue
                    pos = rec.get("Position")
                    try:
                        p = float(pos) if pos is not None and pd.notna(pos) else float(i + 1)
                    except (TypeError, ValueError):
                        p = float(i + 1)
                    frac = ((p - 1.0) * 0.012) % 1.0
                    px, py = point_at_path_frac(cmap.x, cmap.y, frac)
                    last_for_driver = last_lap_by_code.get(code, max_lap)
                    laps_out[str(lap_no)].append(
                        SessionCarPosition(
                            driver_code=code,
                            x=px,
                            y=py,
                            team_colour=team_by_code.get(code),
                            is_pitted=False,
                            is_dnf=last_for_driver < max_lap and lap_no > last_for_driver,
                            path_frac=frac,
                        )
                    )

        return SessionPositionsAllResponse(
            year=year,
            round_number=round_number,
            session_type=session_type.upper(),
            laps=laps_out,
            circuit_path=CircuitPathXY(x=list(cmap.x), y=list(cmap.y)) if cmap.x and cmap.y else None,
        )
    except Exception as extra:
        _log.warning("session_positions_all failed for %s R%s: %s", year, round_number, extra)
        return empty


def _snapshot_at_lap(year: int, round_number: int, lap: int, total_laps: int):
    from aris.commentary import DriverSnap, FieldSnapshot

    raw = timing_at_lap(year, round_number, "R", lap)
    stints = session_stints(year, round_number, "R").stints
    stint_no: dict[str, int] = {}
    compound: dict[str, str | None] = {}
    for s in stints:
        if s.lap_start <= lap <= s.lap_end:
            stint_no[s.driver_code] = s.stint_number
            compound[s.driver_code] = s.compound
    drivers: list[DriverSnap] = []
    ordered = sorted(raw, key=lambda r: r.get("position") or 99)
    for i, r in enumerate(ordered):
        code = str(r["driver_code"])
        gap_ahead = None
        if i > 0:
            g0 = ordered[i - 1].get("gap_to_leader_s")
            g1 = r.get("gap_to_leader_s")
            if g0 is not None and g1 is not None:
                gap_ahead = float(g1) - float(g0)
        drivers.append(
            DriverSnap(
                code=code,
                position=r.get("position"),
                gap_to_leader_s=r.get("gap_to_leader_s"),
                gap_ahead_s=gap_ahead,
                compound=compound.get(code) or r.get("compound"),
                tyre_life=r.get("tyre_life"),
                stint_number=stint_no.get(code),
                last_lap_ms=r.get("last_lap_ms"),
                best_lap_ms=r.get("best_lap_ms"),
            )
        )
    msgs = []
    try:
        for m in session_messages(year, round_number, "R").messages:
            if m.lap == lap:
                msgs.append({"lap": m.lap, "flag": m.flag, "category": m.category, "message": m.message})
    except Exception:
        msgs = []
    return FieldSnapshot(lap=lap, total_laps=total_laps, drivers=drivers, messages=msgs)


def session_events(
    year: int, round_number: int, session_type: str, lap: int, focus_driver: str = "NOR"
) -> SessionEventsResponse:
    from aris.commentary import events_for_transition
    from aris.tracks import load_track_config
    from backend.calendar import get_round

    try:
        rnd = get_round(year, round_number)
        cfg = load_track_config(rnd.country, year=year, round_no=round_number)
        total = cfg.total_laps
        pit_loss_s: float | None = cfg.pit_loss_s
    except Exception:
        cfg = None
        total = 72
        pit_loss_s = None

    from aris.physics.tires import DEFAULT_COMPOUND_SLOPE, normalize_compound

    deg_rate_s: float | None = DEFAULT_COMPOUND_SLOPE.get("MEDIUM", 0.05)
    prev = _snapshot_at_lap(year, round_number, max(1, lap - 1), total) if lap > 1 else None
    current = _snapshot_at_lap(year, round_number, lap, total)
    if cfg is not None:
        focus = current.get_driver((focus_driver or "").upper())
        if focus and focus.compound:
            key = normalize_compound(focus.compound)
            slopes = cfg.compound_slopes or DEFAULT_COMPOUND_SLOPE
            deg_rate_s = float(slopes.get(key, DEFAULT_COMPOUND_SLOPE.get(key, 0.05)))
    msgs = events_for_transition(
        prev, current, focus_driver, pit_loss_s=pit_loss_s, deg_rate_s=deg_rate_s
    )
    # Deduplicate identical texts in one lap (SC messages can repeat).
    seen: set[str] = set()
    events: list[CommentaryEvent] = []
    for m in msgs:
        if m.text in seen:
            continue
        seen.add(m.text)
        events.append(CommentaryEvent(type=m.type.lower() if m.type != "INTEL" else "intel", text=m.text))
    return SessionEventsResponse(
        year=year,
        round_number=round_number,
        session_type=session_type.upper(),
        lap=lap,
        events=events,
    )
