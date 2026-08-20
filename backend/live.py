"""OpenF1 live polling (async httpx), SSE stream, and replay-as-if-live."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.cache import TTL_LIVE, TTL_WEATHER_LIVE, cache
from backend.calendar import now_utc
from backend.models import (
    LiveInterval,
    LiveIntervalsResponse,
    LivePosition,
    LivePositionsResponse,
    LiveRaceControlResponse,
    LiveStatus,
    LiveStintsResponse,
    LiveTimingResponse,
    LiveTimingRow,
    LiveWeatherResponse,
    RaceControlMessage,
    StintRow,
)
from backend.utils import run_sync

OPENF1_BASE = "https://api.openf1.org/v1"

_STATE: dict[str, Any] = {
    "status": None,
    "timing": None,
    "positions": None,
    "intervals": None,
    "race_control": None,
    "stints": None,
    "weather": None,
    "last_success": None,
}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _session_type_map(name: str, stype: str) -> str:
    blob = f"{name} {stype}".lower()
    if "race" in blob and "sprint" not in blob:
        return "R"
    if "sprint quali" in blob or "sprint shootout" in blob:
        return "SQ"
    if "sprint" in blob:
        return "S"
    if "quali" in blob:
        return "Q"
    if "practice 1" in blob or "fp1" in blob:
        return "FP1"
    if "practice 2" in blob or "fp2" in blob:
        return "FP2"
    if "practice 3" in blob or "fp3" in blob:
        return "FP3"
    return (stype or name or "UNKNOWN")[:4].upper()


async def _openf1(path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(f"{OPENF1_BASE}/{path.lstrip('/')}", params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return []


async def get_live_timing_raw(session_key: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{OPENF1_BASE}/intervals", params={"session_key": session_key})
        r.raise_for_status()
        return r.json()


async def get_live_positions_raw(session_key: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{OPENF1_BASE}/position", params={"session_key": session_key})
        r.raise_for_status()
        return r.json()


async def peek_live_session(as_of: datetime | None = None) -> dict[str, Any] | None:
    as_of = now_utc(as_of)
    year = as_of.year
    cache_key = f"openf1:sessions:{year}"
    sessions = cache.get(cache_key, TTL_LIVE)
    if sessions is None:
        try:
            data = await _openf1("sessions", {"year": year})
            sessions = data if isinstance(data, list) else []
            cache.set(cache_key, sessions)
        except Exception:
            sessions = []
    hits: list[tuple[float, dict[str, Any]]] = []
    for sess in sessions:
        start = _parse_dt(sess.get("date_start"))
        end = _parse_dt(sess.get("date_end"))
        if start is None:
            continue
        if end is None:
            end = start + timedelta(hours=3)
        if start <= as_of <= end:
            hits.append(((end - start).total_seconds(), sess))
    hits.sort(key=lambda x: x[0])
    return hits[0][1] if hits else None


async def peek_live_round(as_of: datetime | None = None) -> tuple[int, int] | None:
    """Best-effort (year, round) for a live OpenF1 session, else None."""
    sess = await peek_live_session(as_of)
    if not sess:
        return None
    year = int(sess.get("year") or now_utc(as_of).year)
    meeting_key = sess.get("meeting_key")
    mkey = f"openf1:meetings:{year}"
    meetings = cache.get(mkey, TTL_LIVE * 20)
    if meetings is None:
        try:
            meetings = await _openf1("meetings", {"year": year}) or []
            cache.set(mkey, meetings)
        except Exception:
            meetings = []
    name = ""
    for m in meetings if isinstance(meetings, list) else []:
        if m.get("meeting_key") == meeting_key:
            name = str(m.get("meeting_name") or m.get("circuit_short_name") or "")
            break
    circuit = str(sess.get("circuit_short_name") or sess.get("location") or "").lower()
    needle = (circuit or name.lower()).strip()
    if not needle:
        return None
    try:
        from backend.calendar import _schedule_from_fastf1

        sched = await run_sync(_schedule_from_fastf1, year)
        for _, row in sched.iterrows():
            location = str(row.get("Location") or "").lower()
            event = str(row.get("EventName") or "").lower()
            official = str(row.get("OfficialEventName") or "").lower()
            country = str(row.get("Country") or "").lower()
            blob = f"{location} {event} {official} {country}"
            if circuit and (circuit in blob or location and location in circuit):
                return year, int(row["RoundNumber"])
            if not circuit and name:
                if name.lower() in blob:
                    return year, int(row["RoundNumber"])
    except Exception:
        return None
    return None


async def _driver_code_map(session_key: int) -> dict[int, str]:
    key = f"openf1:drivers:{session_key}"
    rows = cache.get(key, 3600)
    if rows is None:
        try:
            data = await _openf1("drivers", {"session_key": session_key})
            rows = data if isinstance(data, list) else []
            cache.set(key, rows)
        except Exception:
            rows = []
    out: dict[int, str] = {}
    for row in rows:
        num = row.get("driver_number")
        code = row.get("name_acronym") or row.get("broadcast_name")
        if num is not None and code:
            out[int(num)] = str(code)[:3].upper()
    return out


def _compound_letter(raw: str | None) -> str | None:
    if not raw:
        return None
    u = str(raw).upper()
    if u.startswith("SOFT"):
        return "S"
    if u.startswith("MED"):
        return "M"
    if u.startswith("HARD"):
        return "H"
    if u.startswith("INTER"):
        return "I"
    if u.startswith("WET") or u.startswith("FULL"):
        return "W"
    if u in {"S", "M", "H", "I", "W"}:
        return u
    return u[:1]


def _fastf1_window_live(as_of: datetime) -> LiveStatus | None:
    """If OpenF1 has no overlapping session, use FastF1 calendar session windows."""
    from backend.calendar import get_calendar, get_round_sessions

    for year in (as_of.year, as_of.year - 1):
        if year < 2024 or year > 2026:
            continue
        try:
            cal = get_calendar(year, as_of=as_of)
        except Exception:
            continue
        for rnd in cal.rounds:
            if rnd.status != "LIVE":
                continue
            try:
                weekend = get_round_sessions(year, rnd.round_number, as_of=as_of)
            except Exception:
                continue
            live_s = next((s for s in weekend.sessions if s.status == "LIVE"), None)
            if live_s is None:
                started = [
                    s
                    for s in weekend.sessions
                    if s.datetime_utc is not None and s.datetime_utc <= as_of
                ]
                live_s = max(started, key=lambda s: s.datetime_utc or as_of) if started else None
            if live_s is None:
                continue
            elapsed = None
            if live_s.datetime_utc is not None:
                elapsed = max(0, int((as_of - live_s.datetime_utc).total_seconds()))
            openf1_names = {
                "FP1": "Practice 1",
                "FP2": "Practice 2",
                "FP3": "Practice 3",
                "Q": "Qualifying",
                "SQ": "Sprint Qualifying",
                "S": "Sprint",
                "R": "Race",
            }
            stype = openf1_names.get(live_s.session_type, live_s.session_name or live_s.session_type)
            return LiveStatus(
                is_live=True,
                year=year,
                round_number=rnd.round_number,
                session_type=stype,
                session_name=live_s.session_name or stype,
                gp_name=rnd.name,
                session_elapsed_seconds=elapsed,
                last_success_utc=_STATE.get("last_success"),
                replay_mode=False,
                session={
                    "session_type": stype,
                    "session_name": live_s.session_name or stype,
                    "year": year,
                    "round_number": rnd.round_number,
                },
            )
    return None


def simulated_status(as_of: datetime) -> LiveStatus:
    """Pure local asOf simulation — calendar session windows only, no OpenF1."""
    as_of = now_utc(as_of)
    from backend.calendar import get_calendar

    years = [as_of.year]
    if as_of.year < 2024:
        years = [2024]
    if as_of.year > 2026:
        years = [2026]

    for year in years:
        if year < 2024 or year > 2026:
            continue
        try:
            # Use the pre-warmed calendar (no as_of) so this is date arithmetic only.
            cal = get_calendar(year)
        except Exception:
            continue
        for rnd in cal.rounds:
            for sess in rnd.sessions:
                start = sess.date_start
                end = sess.date_end
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                if start <= as_of <= end:
                    elapsed = max(0, int((as_of - start).total_seconds()))
                    return LiveStatus(
                        is_live=True,
                        year=year,
                        round_number=rnd.round_number,
                        session_type=sess.type,
                        session_name=sess.type,
                        gp_name=rnd.name,
                        circuit=rnd.circuit_name,
                        session_elapsed_seconds=elapsed,
                        last_success_utc=_STATE.get("last_success"),
                        replay_mode=False,
                        simulated=True,
                        as_of=as_of,
                        session={
                            "session_type": sess.type,
                            "session_name": sess.type,
                            "year": year,
                            "round_number": rnd.round_number,
                            "circuit": rnd.circuit_name,
                        },
                    )
    return LiveStatus(
        is_live=False,
        session=None,
        simulated=True,
        as_of=as_of,
        last_success_utc=_STATE.get("last_success"),
    )


async def live_status(
    as_of: datetime | None = None,
    *,
    replay_session_key: int | None = None,
    simulated: bool = False,
) -> LiveStatus:
    as_of = now_utc(as_of)
    if replay_session_key:
        return LiveStatus(
            is_live=True,
            session_key=replay_session_key,
            session_type="R",
            session_name="Replay",
            replay_mode=True,
            last_success_utc=_STATE.get("last_success"),
            session={"session_key": replay_session_key, "session_type": "Replay"},
        )
    if simulated:
        return await run_sync(simulated_status, as_of)

    openf1_error: str | None = None
    try:
        local = await run_sync(_fastf1_window_live, as_of)
    except Exception:
        local = None

    sess = None
    if local is not None:
        try:
            sess = await peek_live_session(as_of)
        except Exception as extra:
            sess = None
            openf1_error = str(extra)

    if not sess:
        if local is not None:
            return local
        return LiveStatus(
            is_live=False,
            session=None,
            last_success_utc=_STATE.get("last_success"),
            error=openf1_error,
        )
    year = int(sess.get("year") or as_of.year)
    rnd = await peek_live_round(as_of)
    raw_name = str(sess.get("session_name") or "")
    stype = raw_name or _session_type_map(raw_name, str(sess.get("session_type") or ""))
    start = _parse_dt(sess.get("date_start"))
    elapsed = None
    if start is not None:
        elapsed = max(0, int((as_of - start).total_seconds()))
    flag: str = "GREEN"
    try:
        key = sess.get("session_key")
        rc_key = f"openf1:rc-flag:{key}"
        rc = cache.get(rc_key, TTL_LIVE)
        if rc is None:
            rc = await _openf1("race_control", {"session_key": key}) or []
            cache.set(rc_key, rc)
        if isinstance(rc, list) and rc:
            last = rc[-1]
            cat = str(last.get("category") or last.get("flag") or "").upper()
            if "RED" in cat:
                flag = "RED"
            elif "VSC" in cat:
                flag = "VSC"
            elif "SAFETY" in cat or cat == "SC":
                flag = "SC"
    except Exception:
        pass
    return LiveStatus(
        is_live=True,
        year=year,
        round_number=rnd[1] if rnd else None,
        session_type=stype,
        session_name=raw_name or stype,
        session_key=int(sess["session_key"]) if sess.get("session_key") is not None else None,
        gp_name=str(sess.get("circuit_short_name") or sess.get("location") or ""),
        session_elapsed_seconds=elapsed,
        session_flag=flag,  # type: ignore[arg-type]
        last_success_utc=_STATE.get("last_success"),
        replay_mode=False,
        session=sess,
    )


async def _timing_from_openf1(session_key: int) -> list[LiveTimingRow]:
    codes = await _driver_code_map(session_key)
    positions, intervals, laps, stints = await asyncio.gather(
        _openf1("position", {"session_key": session_key}),
        _openf1("intervals", {"session_key": session_key}),
        _openf1("laps", {"session_key": session_key}),
        _openf1("stints", {"session_key": session_key}),
    )
    latest_pos: dict[int, int] = {}
    if isinstance(positions, list):
        for row in positions:
            num = row.get("driver_number")
            pos = row.get("position")
            if num is None or pos is None:
                continue
            latest_pos[int(num)] = int(pos)
    latest_int: dict[int, dict[str, Any]] = {}
    if isinstance(intervals, list):
        for row in intervals:
            num = row.get("driver_number")
            if num is None:
                continue
            latest_int[int(num)] = row
    last_lap: dict[int, dict[str, Any]] = {}
    best_ms: dict[int, int] = {}
    if isinstance(laps, list):
        for row in laps:
            num = row.get("driver_number")
            if num is None:
                continue
            n = int(num)
            last_lap[n] = row
            dur = row.get("lap_duration")
            if dur:
                ms = int(float(dur) * 1000)
                if n not in best_ms or ms < best_ms[n]:
                    best_ms[n] = ms
    stint_of: dict[int, dict[str, Any]] = {}
    pit_count: dict[int, int] = {}
    if isinstance(stints, list):
        for row in stints:
            num = row.get("driver_number")
            if num is None:
                continue
            n = int(num)
            stint_of[n] = row
            pit_count[n] = pit_count.get(n, 0) + (1 if row.get("stint_number", 1) > 1 else 0)
    rows: list[LiveTimingRow] = []
    numbers = sorted(set(latest_pos) | set(last_lap) | set(codes), key=lambda n: latest_pos.get(n, 99))
    for num in numbers:
        lap = last_lap.get(num) or {}
        iv = latest_int.get(num) or {}
        st = stint_of.get(num) or {}
        last_ms = int(float(lap["lap_duration"]) * 1000) if lap.get("lap_duration") else None

        def _sec(key: str, lap_row: dict[str, Any] = lap) -> int | None:
            val = lap_row.get(key)
            return int(float(val) * 1000) if val else None

        rows.append(
            LiveTimingRow(
                position=latest_pos.get(num, len(rows) + 1),
                driver_code=codes.get(num, f"D{num}"),
                gap_to_leader_s=_float(iv.get("gap_to_leader")),
                gap_to_ahead_s=_float(iv.get("interval")),
                last_lap_ms=last_ms,
                best_lap_ms=best_ms.get(num),
                sector1_ms=_sec("duration_sector_1"),
                sector2_ms=_sec("duration_sector_2"),
                sector3_ms=_sec("duration_sector_3"),
                compound=_compound_letter(st.get("compound")),
                tyre_life=st.get("tyre_age_at_start"),
                stint_number=st.get("stint_number"),
                pit_count=pit_count.get(num, 0),
            )
        )
    rows.sort(key=lambda r: r.position)
    return rows


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def live_timing(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveTimingResponse:
    status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveTimingResponse(is_live=False, rows=[], last_success_utc=status.last_success_utc)
    try:
        tkey = f"openf1:timing:{status.session_key}"
        rows = cache.get(tkey, TTL_LIVE)
        if rows is None:
            rows = await _timing_from_openf1(status.session_key or 0)
            cache.set(tkey, rows)
        _STATE["last_success"] = now_utc(as_of)
        return LiveTimingResponse(
            is_live=True,
            session_key=status.session_key,
            rows=rows,
            last_success_utc=_STATE["last_success"],
        )
    except Exception:
        return LiveTimingResponse(
            is_live=True,
            session_key=status.session_key,
            rows=[],
            last_success_utc=_STATE.get("last_success"),
        )


async def live_positions(
    as_of: datetime | None = None, replay_session_key: int | None = None, simulated: bool = False
) -> LivePositionsResponse:
    from backend.models import CircuitPathXY
    from backend.sessions import circuit_map, compute_path_distance

    status = await live_status(as_of, replay_session_key=replay_session_key, simulated=simulated)
    circuit_path = None
    bounds = None
    path_x: list[float] = []
    path_y: list[float] = []
    if status.year and status.round_number:
        try:
            cmap = await run_sync(circuit_map, status.year, status.round_number)
            if cmap.available and cmap.x and cmap.y:
                circuit_path = CircuitPathXY(x=cmap.x, y=cmap.y)
                bounds = cmap.bounds
                path_x, path_y = cmap.x, cmap.y
        except Exception:
            pass

    if not status.is_live or status.session_key is None:
        return LivePositionsResponse(
            is_live=bool(status.is_live),
            positions=[],
            last_success_utc=status.last_success_utc,
            circuit_path=circuit_path,
        )
    codes = await _driver_code_map(status.session_key)
    try:
        loc = await _openf1("location", {"session_key": status.session_key})
    except Exception:
        loc = []
    latest: dict[int, dict[str, Any]] = {}
    if isinstance(loc, list):
        for row in loc:
            num = row.get("driver_number")
            if num is None:
                continue
            latest[int(num)] = row
    positions: list[LivePosition] = []
    for num, row in latest.items():
        raw_x = float(row.get("x") or 0)
        raw_y = float(row.get("y") or 0)
        if bounds is not None:
            from backend.sessions import _apply_bounds

            px, py = _apply_bounds(raw_x, raw_y, bounds)
        else:
            px, py = raw_x, raw_y
        frac = 0.0
        if path_x and path_y:
            try:
                frac = float(compute_path_distance(px, py, path_x, path_y))
            except Exception:
                frac = 0.0
        positions.append(
            LivePosition(
                driver_code=codes.get(num, f"D{num}"),
                x=px,
                y=py,
                path_frac=frac,
                team_colour=None,
            )
        )
    return LivePositionsResponse(
        is_live=True,
        positions=positions,
        last_success_utc=_STATE.get("last_success"),
        circuit_path=circuit_path,
    )


async def live_intervals(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveIntervalsResponse:
    timing = await live_timing(as_of, replay_session_key=replay_session_key)
    return LiveIntervalsResponse(
        is_live=timing.is_live,
        intervals=[
            LiveInterval(
                driver_code=r.driver_code,
                gap_to_leader_s=r.gap_to_leader_s,
                gap_to_ahead_s=r.gap_to_ahead_s,
            )
            for r in timing.rows
        ],
    )


async def live_race_control(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveRaceControlResponse:
    status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveRaceControlResponse(is_live=False, messages=[])
    try:
        raw = await _openf1("race_control", {"session_key": status.session_key})
    except Exception:
        raw = []
    messages: list[RaceControlMessage] = []
    if isinstance(raw, list):
        for row in raw:
            messages.append(
                RaceControlMessage(
                    utc_time=str(row.get("date") or ""),
                    lap=row.get("lap_number"),
                    flag=row.get("flag") or row.get("category"),
                    category=row.get("category"),
                    message=str(row.get("message") or ""),
                )
            )
    return LiveRaceControlResponse(is_live=True, messages=messages)


async def live_stints(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveStintsResponse:
    status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveStintsResponse(is_live=False, stints=[])
    codes = await _driver_code_map(status.session_key)
    try:
        raw = await _openf1("stints", {"session_key": status.session_key})
    except Exception:
        raw = []
    stints: list[StintRow] = []
    if isinstance(raw, list):
        for row in raw:
            num = row.get("driver_number")
            code = codes.get(int(num), f"D{num}") if num is not None else "?"
            start = int(row.get("lap_start") or 1)
            end = int(row.get("lap_end") or start)
            stints.append(
                StintRow(
                    driver_code=code,
                    stint_number=int(row.get("stint_number") or 1),
                    compound=row.get("compound"),
                    fresh_tyre=None,
                    lap_start=start,
                    lap_end=end,
                    total_laps=max(0, end - start + 1),
                    average_lap_ms=None,
                    deg_rate_ms_per_lap=None,
                )
            )
    return LiveStintsResponse(is_live=True, stints=stints)


async def live_weather(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveWeatherResponse:
    status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveWeatherResponse(is_live=False)
    wkey = f"openf1:weather:{status.session_key}"
    raw = cache.get(wkey, TTL_WEATHER_LIVE)
    if raw is None:
        try:
            raw = await _openf1("weather", {"session_key": status.session_key}) or []
            cache.set(wkey, raw)
        except Exception:
            raw = []
    last = raw[-1] if isinstance(raw, list) and raw else {}
    return LiveWeatherResponse(
        is_live=True,
        air_temp=_float(last.get("air_temperature")),
        track_temp=_float(last.get("track_temperature")),
        humidity=_float(last.get("humidity")),
        rainfall=bool(last.get("rainfall")) if last.get("rainfall") is not None else None,
        wind_speed=_float(last.get("wind_speed")),
        wind_direction=_float(last.get("wind_direction")),
        last_success_utc=_STATE.get("last_success"),
    )


async def sse_generator(replay_session_key: int | None = None):
    while True:
        status = await live_status(replay_session_key=replay_session_key)
        timing = await live_timing(replay_session_key=replay_session_key)
        payload = {
            "status": status.model_dump(mode="json"),
            "timing": timing.model_dump(mode="json"),
        }
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(5 if not status.is_live else 2)
