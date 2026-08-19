"""FastF1 session loading: laps, summary, stints, telemetry, weather, results, messages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from backend.cache import enable_fastf1_cache
from backend.models import (
    CircuitPathPoint,
    CircuitPathResponse,
    DriverFastest,
    LapRow,
    LapsResponse,
    LiveTimingResponse,
    MessagesResponse,
    RaceControlMessage,
    SectorRecord,
    SessionResultRow,
    SessionResultsResponse,
    SessionSummary,
    StintRow,
    StintsResponse,
    TelemetryResponse,
    WeatherSeries,
    WeatherSummary,
)

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
