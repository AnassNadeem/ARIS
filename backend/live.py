"""OpenF1 live polling (async httpx), SSE stream, and replay-as-if-live."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.cache import TTL_LIVE, TTL_WEATHER_LIVE, cache
from backend.calendar import now_utc
from backend.http_client import aopenf1
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
    QualiWindow,
    RaceControlMessage,
    ReplayFrameResponse,
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
    "session": None,
    "drivers": {},
    "laps": [],
    "latest_pos": {},
    "locations": {},
    "eliminated": set(),
    "error": None,
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


async def _openf1(path: str, params: dict[str, Any] | None = None, *, timeout: float | None = None) -> Any:
    try:
        data = await aopenf1(path, params, timeout=timeout)
        return data if data is not None else []
    except Exception as extra:
        _STATE["error"] = str(extra)
        return []


async def get_live_timing_raw(session_key: int) -> list[dict]:
    data = await _openf1("intervals", {"session_key": session_key})
    return data if isinstance(data, list) else []


async def get_live_positions_raw(session_key: int) -> list[dict]:
    data = await _openf1("position", {"session_key": session_key})
    return data if isinstance(data, list) else []


def _session_window_live(sess: dict[str, Any], as_of: datetime) -> bool:
    start = _parse_dt(sess.get("date_start"))
    end = _parse_dt(sess.get("date_end"))
    if start is None:
        return False
    if end is None:
        end = start + timedelta(hours=2)
    return start - timedelta(minutes=5) <= as_of <= end + timedelta(minutes=8)


async def peek_live_session(as_of: datetime | None = None) -> dict[str, Any] | None:
    as_of = now_utc(as_of)
    cached = _STATE.get("session")
    if isinstance(cached, dict) and _session_window_live(cached, as_of):
        return cached
    try:
        data = await _openf1("sessions", {"session_key": "latest"})
    except Exception:
        data = []
    latest = None
    if isinstance(data, list) and data:
        latest = data[0] if isinstance(data[0], dict) else None
    elif isinstance(data, dict):
        latest = data
    if latest and _session_window_live(latest, as_of):
        _STATE["session"] = latest
        return latest
    year = as_of.year
    cache_key = f"openf1:sessions:{year}"
    sessions = cache.get(cache_key, TTL_LIVE)
    if sessions is None:
        try:
            raw = await _openf1("sessions", {"year": year})
            sessions = raw if isinstance(raw, list) else []
            cache.set(cache_key, sessions)
        except Exception:
            sessions = []
    hits: list[tuple[float, dict[str, Any]]] = []
    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        if _session_window_live(sess, as_of):
            start = _parse_dt(sess.get("date_start"))
            end = _parse_dt(sess.get("date_end")) or (start + timedelta(hours=2) if start else as_of)
            hits.append(((end - start).total_seconds(), sess))
    hits.sort(key=lambda x: x[0])
    if hits:
        _STATE["session"] = hits[0][1]
        return hits[0][1]
    if latest and _session_window_live(latest, as_of):
        return latest
    return None


_OPENF1_SESSION_NAMES = {
    "FP1": ("Practice 1",),
    "FP2": ("Practice 2",),
    "FP3": ("Practice 3",),
    "SQ": ("Sprint Qualifying", "Sprint Shootout"),
    "S": ("Sprint",),
    "Q": ("Qualifying",),
    "R": ("Race",),
}


def _circuit_match(sess: dict[str, Any], rnd: Any) -> bool:
    blob = f"{sess.get('circuit_short_name') or ''} {sess.get('location') or ''} {sess.get('country_name') or ''}".lower()
    for token in (getattr(rnd, "city", None), getattr(rnd, "circuit_name", None), getattr(rnd, "name", None)):
        if token and str(token).lower() in blob:
            return True
    return False


async def resolve_openf1_session(year: int, round_number: int, session_type: str) -> dict[str, Any] | None:
    from backend.calendar import get_round

    rnd = get_round(year, round_number)
    names = _OPENF1_SESSION_NAMES.get(session_type.upper(), (session_type,))
    cache_key = f"openf1:sessions:{year}"
    sessions = cache.get(cache_key, 120)
    if sessions is None:
        raw = await _openf1("sessions", {"year": year})
        sessions = raw if isinstance(raw, list) else []
        cache.set(cache_key, sessions)
    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        if str(sess.get("session_name") or "") not in names:
            continue
        if _circuit_match(sess, rnd) and sess.get("session_key") is not None:
            return sess
    return None


async def resolve_openf1_session_key(year: int, round_number: int, session_type: str) -> int | None:
    sess = await resolve_openf1_session(year, round_number, session_type)
    if sess is None or sess.get("session_key") is None:
        return None
    return int(sess["session_key"])


def _feed_session_key() -> int | None:
    sess = _STATE.get("session")
    if isinstance(sess, dict) and sess.get("session_key") is not None:
        try:
            return int(sess["session_key"])
        except (TypeError, ValueError):
            return None
    return None


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


async def _driver_rows(session_key: int) -> list[dict[str, Any]]:
    cached = _STATE.get("drivers")
    if isinstance(cached, dict) and cached.get("_session_key") == session_key:
        return list(cached.get("rows") or [])
    key = f"openf1:drivers:{session_key}"
    rows = cache.get(key, 3600)
    if rows is None:
        data = await _openf1("drivers", {"session_key": session_key})
        rows = data if isinstance(data, list) else []
        cache.set(key, rows)
    _STATE["drivers"] = {"_session_key": session_key, "rows": rows}
    return rows


async def _driver_code_map(session_key: int) -> dict[int, str]:
    out: dict[int, str] = {}
    colours: dict[int, str] = {}
    for row in await _driver_rows(session_key):
        num = row.get("driver_number")
        code = row.get("name_acronym") or row.get("broadcast_name")
        if num is None or not code:
            continue
        n = int(num)
        out[n] = str(code)[:3].upper()
        colour = row.get("team_colour")
        if colour:
            colours[n] = f"#{str(colour).lstrip('#')}"
    _STATE["driver_colours"] = colours
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
        mapped = "R"
        raw_name = "Replay"
        year = None
        gp = None
        try:
            rows = await _openf1("sessions", {"session_key": replay_session_key})
            row = rows[0] if isinstance(rows, list) and rows else None
            if isinstance(row, dict):
                raw_name = str(row.get("session_name") or "Replay")
                mapped = _session_type_map(raw_name, str(row.get("session_type") or ""))
                year = int(row["year"]) if row.get("year") is not None else None
                gp = str(row.get("circuit_short_name") or row.get("location") or "")
        except Exception:
            row = None
        return LiveStatus(
            is_live=True,
            year=year,
            session_key=replay_session_key,
            session_type=mapped,
            session_name=raw_name,
            gp_name=gp,
            replay_mode=True,
            view_only=mapped not in {"R", "S"},
            last_success_utc=_STATE.get("last_success"),
            session={"session_key": replay_session_key, "session_type": mapped},
        )
    if simulated:
        return await run_sync(simulated_status, as_of)

    openf1_error: str | None = None
    sess = None
    try:
        sess = await peek_live_session(as_of)
    except Exception as extra:
        sess = None
        openf1_error = str(extra)

    local = None
    try:
        local = await run_sync(_fastf1_window_live, as_of)
    except Exception:
        local = None

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
    mapped = _session_type_map(raw_name, str(sess.get("session_type") or ""))
    start = _parse_dt(sess.get("date_start"))
    end = _parse_dt(sess.get("date_end"))
    elapsed = None
    remaining = None
    if start is not None:
        elapsed = max(0, int((as_of - start).total_seconds()))
    if end is not None:
        remaining = max(0, int((end - as_of).total_seconds()))
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
    view_only = mapped in {"SQ", "Q", "FP1", "FP2", "FP3"}
    return LiveStatus(
        is_live=True,
        year=year,
        round_number=(local.round_number if local else None) or (rnd[1] if rnd else None),
        session_type=mapped,
        session_name=raw_name or mapped,
        session_key=int(sess["session_key"]) if sess.get("session_key") is not None else None,
        gp_name=str(sess.get("circuit_short_name") or sess.get("location") or ""),
        circuit=str(sess.get("circuit_short_name") or sess.get("location") or ""),
        session_elapsed_seconds=elapsed,
        session_remaining_seconds=remaining,
        session_flag=flag,  # type: ignore[arg-type]
        last_success_utc=_STATE.get("last_success"),
        replay_mode=False,
        session=sess,
        source="openf1",
        view_only=view_only,
        aris_ready=mapped in {"R", "S"},
        error=_STATE.get("error"),
    )


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sector_colour_from_segments(segments: Any, fallback: str = "grey") -> str:
    if not isinstance(segments, list) or not segments:
        return fallback
    codes = [int(v) for v in segments if v is not None]
    if 2051 in codes:
        return "purple"
    if 2049 in codes:
        return "green"
    if 2048 in codes:
        return "yellow"
    return fallback


def _ms(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value) * 1000))
    except (TypeError, ValueError):
        return None


_REPLAY_PACKS: dict[int, dict[str, Any]] = {}
_REPLAY_LOCK = asyncio.Lock()
_LOC_BUCKETS: dict[tuple[int, int], list[Any]] = {}
_LOC_BUCKET_S = 30


def _laps_upto(laps: list[Any], as_of: datetime | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in laps:
        if not isinstance(row, dict):
            continue
        if as_of is None:
            out.append(row)
            continue
        start = _parse_dt(row.get("date_start"))
        if start is None or start <= as_of:
            out.append(row)
    return out


def _lap_completed(row: dict[str, Any], as_of: datetime | None) -> bool:
    dur = row.get("lap_duration")
    if not dur:
        return False
    if as_of is None:
        return True
    start = _parse_dt(row.get("date_start"))
    if start is None:
        return True
    try:
        end = start + timedelta(seconds=float(dur))
    except (TypeError, ValueError):
        return start <= as_of
    return end <= as_of


def _best_ms_from_laps(laps: list[dict[str, Any]], as_of: datetime | None) -> dict[int, int]:
    best: dict[int, int] = {}
    for row in laps:
        num = row.get("driver_number")
        dur = row.get("lap_duration")
        if num is None or not dur or not _lap_completed(row, as_of):
            continue
        n = int(num)
        ms = int(float(dur) * 1000)
        if n not in best or ms < best[n]:
            best[n] = ms
    return best


def _weather_at(rows: list[Any], as_of: datetime | None) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if as_of is not None and dt is not None and dt > as_of:
            continue
        last = row
    return last


def _latest_by_date(
    rows: list[Any], as_of: datetime | None, *, key: str = "date"
) -> dict[int, dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get(key))
        if as_of is not None and dt is not None and dt > as_of:
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        latest[int(num)] = row
    return latest


def _position_map(rows: list[Any], as_of: datetime | None) -> dict[int, int]:
    latest: dict[int, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if as_of is not None and dt is not None and dt > as_of:
            continue
        num = row.get("driver_number")
        pos = row.get("position")
        if num is None or pos is None:
            continue
        latest[int(num)] = int(pos)
    return latest


def _stints_at(stints: list[Any], last_lap: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    chosen: dict[int, dict[str, Any]] = {}
    for row in stints:
        if not isinstance(row, dict):
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        n = int(num)
        current = int((last_lap.get(n) or {}).get("lap_number") or 0)
        start = int(row.get("lap_start") or 1)
        if current == 0:
            if start <= 1:
                chosen[n] = row
            continue
        if start <= current:
            chosen[n] = row
    return chosen


def _weather_from_row(row: dict[str, Any], *, is_live: bool) -> LiveWeatherResponse:
    rain = row.get("rainfall")
    return LiveWeatherResponse(
        is_live=is_live,
        air_temp=_float(row.get("air_temperature")),
        track_temp=_float(row.get("track_temperature")),
        humidity=_float(row.get("humidity")),
        rainfall=bool(rain) if rain is not None else None,
        wind_speed=_float(row.get("wind_speed")),
        wind_direction=_float(row.get("wind_direction")),
        pressure=_float(row.get("pressure")),
        last_success_utc=_STATE.get("last_success"),
    )


def _timing_rows_from_payload(
    *,
    codes: dict[int, str],
    colours: dict[int, str],
    positions: dict[int, int],
    laps: list[dict[str, Any]],
    stints: list[Any],
    intervals: dict[int, dict[str, Any]],
    eliminated: set[str],
    locations: dict[int, dict[str, Any]],
    as_of: datetime | None = None,
) -> list[LiveTimingRow]:
    last_lap: dict[int, dict[str, Any]] = {}
    for row in laps:
        num = row.get("driver_number")
        if num is None:
            continue
        last_lap[int(num)] = row
    best_ms = _best_ms_from_laps(laps, as_of)
    stint_of = _stints_at(stints if isinstance(stints, list) else [], last_lap)
    pit_count: dict[int, int] = {}
    if isinstance(stints, list):
        for row in stints:
            if not isinstance(row, dict):
                continue
            num = row.get("driver_number")
            if num is None:
                continue
            n = int(num)
            start = int(row.get("lap_start") or 1)
            current = int((last_lap.get(n) or {}).get("lap_number") or 0)
            if current and start <= current and int(row.get("stint_number") or 1) > 1:
                pit_count[n] = pit_count.get(n, 0) + 1
            elif as_of is None and int(row.get("stint_number") or 1) > 1:
                pit_count[n] = pit_count.get(n, 0) + 1
    latest_pos = dict(positions)
    leader_best = min(best_ms.values()) if best_ms else None
    fastest_num = min(best_ms, key=best_ms.get) if best_ms else None  # type: ignore[arg-type]
    numbers = sorted(set(latest_pos) | set(last_lap) | set(codes), key=lambda n: latest_pos.get(n, 99))
    if not latest_pos and best_ms:
        ranked = sorted(best_ms, key=lambda n: best_ms[n])
        latest_pos = {n: i + 1 for i, n in enumerate(ranked)}
        numbers = sorted(set(latest_pos) | set(last_lap) | set(codes), key=lambda n: latest_pos.get(n, 99))
    rows: list[LiveTimingRow] = []
    for num in numbers:
        lap = last_lap.get(num) or {}
        iv = intervals.get(num) or {}
        st = stint_of.get(num) or {}
        last_ms = _ms(lap.get("lap_duration")) if _lap_completed(lap, as_of) else None
        code = codes.get(num, f"D{num}")
        gap_leader = _float(iv.get("gap_to_leader"))
        if gap_leader is None and leader_best is not None and num in best_ms:
            gap_leader = (best_ms[num] - leader_best) / 1000.0
        loc = locations.get(num) or {}
        in_pit = bool(lap.get("is_pit_out_lap")) or str(loc.get("status") or "").lower() in {"pit", "inpit"}
        rows.append(
            LiveTimingRow(
                position=int(latest_pos.get(num, len(rows) + 1)),
                driver_code=code,
                gap_to_leader_s=gap_leader,
                gap_to_ahead_s=_float(iv.get("interval")),
                last_lap_ms=last_ms,
                best_lap_ms=best_ms.get(num),
                sector1_ms=_ms(lap.get("duration_sector_1")),
                sector2_ms=_ms(lap.get("duration_sector_2")),
                sector3_ms=_ms(lap.get("duration_sector_3")),
                s1_colour=_sector_colour_from_segments(lap.get("segments_sector_1")),  # type: ignore[arg-type]
                s2_colour=_sector_colour_from_segments(lap.get("segments_sector_2")),  # type: ignore[arg-type]
                s3_colour=_sector_colour_from_segments(lap.get("segments_sector_3")),  # type: ignore[arg-type]
                compound=_compound_letter(st.get("compound")),
                tyre_life=st.get("tyre_age_at_start"),
                stint_number=st.get("stint_number"),
                pit_count=pit_count.get(num, 0),
                speed_trap_kph=_float(lap.get("st_speed")),
                team_colour=colours.get(num),
                eliminated=code in eliminated,
                in_pit=in_pit,
                fastest_lap=num == fastest_num,
            )
        )
    rows.sort(key=lambda r: (r.position, r.best_lap_ms or 10**9))
    return rows


def _eliminated_codes(messages: list[Any], codes: dict[int, str]) -> set[str]:
    out: set[str] = set()
    by_code = {v.upper(): k for k, v in codes.items()}
    for row in messages:
        if not isinstance(row, dict):
            continue
        blob = f"{row.get('message') or ''} {row.get('flag') or ''} {row.get('category') or ''}".upper()
        if "ELIMINATED" not in blob and " KNOCKED OUT" not in blob:
            continue
        for code in by_code:
            if code and code in blob:
                out.add(code)
    return out


async def _timing_from_openf1(
    session_key: int, as_of: datetime | None = None, *, persist: bool = True
) -> list[LiveTimingRow]:
    codes = await _driver_code_map(session_key)
    colours: dict[int, str] = _STATE.get("driver_colours") or {}
    use_feed = persist and as_of is None and _feed_session_key() == session_key
    positions = _STATE.get("latest_pos") or {} if use_feed else {}
    laps = _STATE.get("laps") if use_feed else None
    stints = _STATE.get("stints") if use_feed else None
    intervals = _STATE.get("intervals") if use_feed else None
    if not isinstance(laps, list) or not laps:
        positions_raw, intervals_raw, laps, stints_raw = await asyncio.gather(
            _openf1("position", {"session_key": session_key}),
            _openf1("intervals", {"session_key": session_key}),
            _openf1("laps", {"session_key": session_key}),
            _openf1("stints", {"session_key": session_key}),
        )
        if isinstance(positions_raw, list):
            positions = _position_map(positions_raw, as_of)
            if persist and as_of is None:
                _STATE["latest_pos"] = positions
        intervals = {}
        if isinstance(intervals_raw, list):
            intervals = _latest_by_date(intervals_raw, as_of)
            if persist and as_of is None:
                _STATE["intervals"] = intervals
        if isinstance(stints_raw, list):
            stints = stints_raw
            if persist and as_of is None:
                _STATE["stints"] = stints
        if isinstance(laps, list) and persist and as_of is None:
            _STATE["laps"] = laps
        if isinstance(positions_raw, list) and as_of is not None:
            positions = _position_map(positions_raw, as_of)
        if isinstance(intervals_raw, list) and as_of is not None:
            intervals = _latest_by_date(intervals_raw, as_of)
    latest_pos = positions if isinstance(positions, dict) else {}
    latest_int = intervals if isinstance(intervals, dict) else {}
    filtered = _laps_upto(laps if isinstance(laps, list) else [], as_of)
    rc = _STATE.get("race_control") or []
    eliminated = _eliminated_codes(rc if isinstance(rc, list) else [], codes)
    stored = _STATE.get("eliminated") or set()
    if isinstance(stored, set) and as_of is None:
        eliminated |= {codes[n] for n in stored if n in codes} | stored
    locations = _STATE.get("locations") or {} if as_of is None else {}
    return _timing_rows_from_payload(
        codes=codes,
        colours=colours if isinstance(colours, dict) else {},
        positions=latest_pos,
        laps=filtered,
        stints=stints if isinstance(stints, list) else [],
        intervals=latest_int,
        eliminated=eliminated,
        locations=locations if isinstance(locations, dict) else {},
        as_of=as_of,
    )


async def _ensure_replay_pack(
    session_key: int, year: int | None = None, round_number: int | None = None
) -> dict[str, Any]:
    cached = _REPLAY_PACKS.get(session_key)
    if cached is not None:
        return cached
    async with _REPLAY_LOCK:
        cached = _REPLAY_PACKS.get(session_key)
        if cached is not None:
            return cached
        sess_rows = await _openf1("sessions", {"session_key": session_key})
        sess = sess_rows[0] if isinstance(sess_rows, list) and sess_rows and isinstance(sess_rows[0], dict) else {}
        from backend.models import CircuitPathXY
        from backend.sessions import build_ff1_replay_assets, circuit_map

        pack_year = year or (int(sess["year"]) if sess.get("year") is not None else None)
        pack_round = round_number
        mapped = _session_type_map(str(sess.get("session_name") or ""), str(sess.get("session_type") or ""))
        circuit_path = None
        bounds = None
        path_x: list[float] = []
        path_y: list[float] = []
        pit_stalls: list[list[float]] = []
        if pack_year and pack_round:
            try:
                cmap = await run_sync(circuit_map, pack_year, pack_round)
                if cmap.available and cmap.x and cmap.y:
                    circuit_path = CircuitPathXY(x=cmap.x, y=cmap.y)
                    bounds = cmap.bounds
                    path_x, path_y = list(cmap.x), list(cmap.y)
                    pit_stalls = [list(p) for p in (cmap.pit_stalls or [])]
            except Exception:
                pass
        start = _parse_dt(sess.get("date_start"))
        end = _parse_dt(sess.get("date_end"))
        if end is None and start is not None:
            end = start + timedelta(hours=1.5)

        ff1: dict[str, Any] = {"ok": False}
        if pack_year and pack_round:
            try:
                ff1 = await run_sync(
                    build_ff1_replay_assets,
                    pack_year,
                    pack_round,
                    mapped,
                    bounds,
                    date_start=start,
                    date_end=end,
                )
            except Exception:
                ff1 = {"ok": False}

        use_ff1 = bool(ff1.get("ok") and ff1.get("pos_samples"))
        laps: Any = ff1.get("laps") if use_ff1 and ff1.get("laps") else None
        weather: Any = ff1.get("weather") if use_ff1 and ff1.get("weather") else None
        stints: Any = []
        positions_raw: Any = []
        intervals_raw: Any = []
        rc_raw: Any = []
        codes = ff1.get("code_by_num") if use_ff1 and ff1.get("code_by_num") else {}
        colours = ff1.get("colours") if use_ff1 and ff1.get("colours") else {}
        if not use_ff1:
            laps, weather, stints, positions_raw, intervals_raw, rc_raw = await asyncio.gather(
                _openf1("laps", {"session_key": session_key}),
                _openf1("weather", {"session_key": session_key}),
                _openf1("stints", {"session_key": session_key}),
                _openf1("position", {"session_key": session_key}),
                _openf1("intervals", {"session_key": session_key}),
                _openf1("race_control", {"session_key": session_key}),
            )
            codes = await _driver_code_map(session_key)
            colours = {}
            try:
                drivers = await _driver_rows(session_key)
                for row in drivers:
                    num = row.get("driver_number")
                    colour = row.get("team_colour")
                    if num is not None and colour:
                        colours[int(num)] = str(colour if str(colour).startswith("#") else f"#{colour}")
            except Exception:
                colours = _STATE.get("driver_colours") or {}
        if not codes:
            try:
                codes = await _driver_code_map(session_key)
            except Exception:
                codes = {}

        pack = {
            "session": sess,
            "laps": laps if isinstance(laps, list) else [],
            "weather": weather if isinstance(weather, list) else [],
            "stints": stints if isinstance(stints, list) else [],
            "positions": positions_raw if isinstance(positions_raw, list) else [],
            "intervals": intervals_raw if isinstance(intervals_raw, list) else [],
            "race_control": rc_raw if isinstance(rc_raw, list) else [],
            "codes": codes,
            "colours": colours if isinstance(colours, dict) else {},
            "date_start": start,
            "date_end": end,
            "year": pack_year,
            "round_number": pack_round,
            "session_type": mapped,
            "circuit_path": circuit_path,
            "bounds": bounds,
            "path_x": path_x,
            "path_y": path_y,
            "pit_stalls": pit_stalls,
            "source": "fastf1" if use_ff1 else "openf1",
            "ff1": ff1 if use_ff1 else {},
        }
        _REPLAY_PACKS[session_key] = pack
        if not use_ff1 and start is not None:
            try:
                await _location_bucket(session_key, start)
            except Exception:
                pass
        return pack


def _trim_loc_buckets() -> None:
    if len(_LOC_BUCKETS) <= 48:
        return
    keys = sorted(_LOC_BUCKETS, key=lambda k: k[1])
    for key in keys[: len(keys) - 36]:
        _LOC_BUCKETS.pop(key, None)


async def _location_bucket(session_key: int, as_of: datetime) -> list[Any]:
    ts = int(as_of.timestamp())
    bucket = ts - (ts % _LOC_BUCKET_S)
    key = (session_key, bucket)
    cached = _LOC_BUCKETS.get(key)
    if cached is not None:
        return cached
    start = datetime.fromtimestamp(bucket, tz=timezone.utc)
    end = start + timedelta(seconds=_LOC_BUCKET_S + 2)
    try:
        data = await _openf1(
            "location",
            {
                "session_key": session_key,
                "date>=": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "date<=": end.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            timeout=30.0,
        )
    except Exception:
        data = []
    rows = data if isinstance(data, list) else []
    _LOC_BUCKETS[key] = rows
    _trim_loc_buckets()
    return rows


def _locations_at(rows: list[Any], as_of: datetime) -> dict[int, dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if dt is not None and dt > as_of:
            continue
        num = row.get("driver_number")
        if num is None:
            continue
        prev = latest.get(int(num))
        prev_dt = _parse_dt(prev.get("date")) if prev else None
        if prev is None or prev_dt is None or (dt is not None and dt >= prev_dt):
            latest[int(num)] = row
    return latest


def _positions_from_locations(
    latest: dict[int, dict[str, Any]],
    *,
    codes: dict[int, str],
    colours: dict[int, str],
    bounds: Any,
    path_x: list[float],
    path_y: list[float],
    eliminated: set[str],
) -> list[LivePosition]:
    from backend.sessions import compute_path_distance

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
        code = codes.get(num, f"D{num}")
        in_pit = str(row.get("status") or "").lower() in {"pit", "inpit"}
        is_dnf = code in eliminated
        reason = None
        if is_dnf:
            reason = "OUT"
        elif in_pit:
            reason = "In pit"
        positions.append(
            LivePosition(
                driver_code=code,
                x=px,
                y=py,
                path_frac=frac,
                team_colour=colours.get(num),
                is_pitted=in_pit,
                is_dnf=is_dnf,
                reason=reason,
            )
        )
    return positions


def _quali_phase(windows: list[dict[str, Any]], elapsed_s: int) -> str | None:
    current = None
    for win in windows:
        if win["start_s"] <= elapsed_s <= win["end_s"]:
            return str(win["id"])
        if elapsed_s >= win["start_s"]:
            current = str(win["id"])
    return current


def _driver_reason(
    *,
    code: str,
    has_sample: bool,
    in_pit: bool,
    eliminated: bool,
    status: str,
    phase: str | None,
    q_times: dict[str, int | None] | None,
    started: bool,
) -> str | None:
    st = (status or "").lower()
    if "not start" in st or st == "dns":
        return "DNS"
    if any(tok in st for tok in ("retired", "dnf", "accident", "collision", "withdrew")):
        return "DNF"
    if eliminated:
        if phase and q_times:
            if phase in {"Q2", "SQ2"} and not q_times.get("q2_ms"):
                return "OUT Q1"
            if phase in {"Q3", "SQ3"} and not q_times.get("q3_ms"):
                return "OUT Q2" if q_times.get("q2_ms") else "OUT Q1"
        return "OUT"
    if not started or not has_sample:
        return "Not started"
    if in_pit:
        return "In pit"
    return None


async def replay_frame(
    session_key: int,
    as_of: datetime,
    *,
    year: int | None = None,
    round_number: int | None = None,
) -> ReplayFrameResponse:
    pack = await _ensure_replay_pack(session_key, year, round_number)
    start: datetime | None = pack.get("date_start")
    end: datetime | None = pack.get("date_end")
    clock = now_utc(as_of)
    if start is not None and clock < start:
        clock = start
    if end is not None and clock > end:
        clock = end
    duration = int((end - start).total_seconds()) if start and end else 0
    elapsed = int((clock - start).total_seconds()) if start else 0
    ff1 = pack.get("ff1") or {}
    source = str(pack.get("source") or "openf1")
    windows_raw = ff1.get("quali_windows") or []
    phase = _quali_phase(windows_raw, elapsed) if windows_raw else None
    laps = _laps_upto(pack.get("laps") or [], clock)
    weather_row = _weather_at(pack.get("weather") or [], clock)
    rc_upto = []
    for row in pack.get("race_control") or []:
        if not isinstance(row, dict):
            continue
        dt = _parse_dt(row.get("date"))
        if dt is None or dt <= clock:
            rc_upto.append(row)
    codes: dict[int, str] = pack.get("codes") or {}
    eliminated = _eliminated_codes(rc_upto, codes)
    q_times: dict[str, dict[str, int | None]] = ff1.get("q_times") or {}
    status_by = ff1.get("status_by_code") or {}
    if phase:
        for code, qt in q_times.items():
            if phase in {"Q2", "SQ2"} and not qt.get("q2_ms") and not qt.get("q3_ms"):
                eliminated.add(code)
            if phase in {"Q3", "SQ3"} and not qt.get("q3_ms"):
                eliminated.add(code)
    locations: dict[int, dict[str, Any]] = {}
    if source != "fastf1":
        loc_rows = await _location_bucket(session_key, clock)
        locations = _locations_at(loc_rows, clock)
        if not locations:
            earlier = clock - timedelta(seconds=_LOC_BUCKET_S)
            loc_rows = await _location_bucket(session_key, earlier)
            locations = _locations_at(loc_rows, clock)
        next_clock = clock + timedelta(seconds=_LOC_BUCKET_S)
        if end is None or next_clock <= end:
            async def _prefetch() -> None:
                try:
                    await _location_bucket(session_key, next_clock)
                except Exception:
                    pass

            asyncio.create_task(_prefetch())
    timing_rows = _timing_rows_from_payload(
        codes=codes,
        colours=pack.get("colours") or {},
        positions=_position_map(pack.get("positions") or [], clock),
        laps=laps,
        stints=pack.get("stints") or [],
        intervals=_latest_by_date(pack.get("intervals") or [], clock),
        eliminated=eliminated,
        locations=locations,
        as_of=clock,
    )
    stalls: list[list[float]] = pack.get("pit_stalls") or []
    from backend.sessions import compute_path_distance, sample_ff1_position

    path_x = pack.get("path_x") or []
    path_y = pack.get("path_y") or []
    colours: dict[int, str] = pack.get("colours") or {}
    num_by_code: dict[str, int] = ff1.get("num_by_code") or {v: k for k, v in codes.items()}
    pos_samples: dict[str, list[Any]] = ff1.get("pos_samples") or {}
    positions: list[LivePosition] = []
    seen: set[str] = set()
    t_epoch = clock.timestamp()
    all_codes = sorted(set(num_by_code) | set(status_by) | {r.driver_code for r in timing_rows} | set(pos_samples))
    for i, code in enumerate(all_codes):
        num = num_by_code.get(code)
        sample = sample_ff1_position(pos_samples.get(code) or [], t_epoch) if source == "fastf1" else None
        started = any(int(r.get("driver_number") or -1) == num for r in laps if num is not None) or sample is not None
        in_pit = False
        is_dnf = code in eliminated
        px = py = None
        frac = 0.0
        st_txt = ""
        if sample is not None:
            px, py, st_txt = sample
            in_pit = "pit" in st_txt.lower()
            if path_x and path_y:
                try:
                    frac = float(compute_path_distance(px, py, path_x, path_y))
                except Exception:
                    frac = 0.0
        elif num is not None and num in locations:
            row = locations[num]
            raw_x = float(row.get("x") or 0)
            raw_y = float(row.get("y") or 0)
            bounds = pack.get("bounds")
            if bounds is not None:
                from backend.sessions import _apply_bounds

                px, py = _apply_bounds(raw_x, raw_y, bounds)
            else:
                px, py = raw_x, raw_y
            in_pit = str(row.get("status") or "").lower() in {"pit", "inpit"}
            if path_x and path_y:
                try:
                    frac = float(compute_path_distance(px, py, path_x, path_y))
                except Exception:
                    frac = 0.0
        reason = _driver_reason(
            code=code,
            has_sample=sample is not None or (num is not None and num in locations),
            in_pit=in_pit,
            eliminated=is_dnf,
            status=str(status_by.get(code) or ""),
            phase=phase,
            q_times=q_times.get(code),
            started=started,
        )
        if reason in {"DNS", "DNF", "Not started", "OUT", "OUT Q1", "OUT Q2"} or in_pit:
            in_pit = True
            if stalls:
                stall = stalls[i % len(stalls)]
                px, py = float(stall[0]), float(stall[1])
            elif path_x:
                px, py = float(path_x[0]), float(path_y[0])
            frac = 0.0
        if px is None or py is None:
            continue
        seen.add(code)
        qt = q_times.get(code) or {}
        positions.append(
            LivePosition(
                driver_code=code,
                x=px,
                y=py,
                path_frac=frac,
                team_colour=colours.get(num) if num is not None else None,
                is_pitted=in_pit,
                is_dnf=is_dnf or reason in {"DNF", "DNS"},
                reason=reason,
            )
        )
        for row in timing_rows:
            if row.driver_code != code:
                continue
            row.reason = reason
            row.in_pit = in_pit or row.in_pit
            row.eliminated = is_dnf or row.eliminated
            row.q1_ms = qt.get("q1_ms")
            row.q2_ms = qt.get("q2_ms")
            row.q3_ms = qt.get("q3_ms")
    current_lap = None
    if laps:
        try:
            current_lap = max(int(r.get("lap_number") or 0) for r in laps)
        except (TypeError, ValueError):
            current_lap = None
    weather = _weather_from_row(weather_row, is_live=True)
    quali_windows = [QualiWindow(**w) for w in windows_raw if isinstance(w, dict) and "id" in w]
    return ReplayFrameResponse(
        session_key=session_key,
        as_of=clock,
        elapsed_s=max(0, elapsed),
        duration_s=max(0, duration),
        date_start=start,
        date_end=end,
        timing=LiveTimingResponse(
            is_live=True,
            session_key=session_key,
            rows=timing_rows,
            last_success_utc=clock,
            current_lap=current_lap,
        ),
        weather=weather,
        positions=LivePositionsResponse(
            is_live=True,
            positions=positions,
            last_success_utc=clock,
            circuit_path=pack.get("circuit_path"),
        ),
        source=source,
        quali_phase=phase,
        quali_windows=quali_windows,
    )


async def live_timing(
    as_of: datetime | None = None, replay_session_key: int | None = None
) -> LiveTimingResponse:
    if replay_session_key is not None and as_of is not None:
        frame = await replay_frame(replay_session_key, as_of)
        return frame.timing
    status = await live_status(as_of, replay_session_key=replay_session_key)
    if not status.is_live or status.session_key is None:
        return LiveTimingResponse(is_live=False, rows=[], last_success_utc=status.last_success_utc)
    try:
        tkey = f"openf1:timing:{status.session_key}"
        rows = None if as_of is not None else cache.get(tkey, TTL_LIVE)
        if rows is None:
            rows = await _timing_from_openf1(status.session_key or 0, as_of, persist=as_of is None)
            if as_of is None:
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
    if replay_session_key is not None and as_of is not None:
        frame = await replay_frame(replay_session_key, as_of)
        return frame.positions
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
    colours: dict[int, str] = _STATE.get("driver_colours") or {}
    latest: dict[int, dict[str, Any]] = dict(_STATE.get("locations") or {}) if _feed_session_key() == status.session_key else {}
    if not latest:
        now = now_utc(as_of)
        loc: list[Any] = []
        windows = (8, 120, 600)
        sess_row = _STATE.get("session") if _feed_session_key() == status.session_key else None
        end = _parse_dt((sess_row or {}).get("date_end")) if isinstance(sess_row, dict) else None
        if end is None:
            meta = await _openf1("sessions", {"session_key": status.session_key})
            if isinstance(meta, list) and meta and isinstance(meta[0], dict):
                end = _parse_dt(meta[0].get("date_end"))
        if end is not None and end < now:
            since = (end - timedelta(seconds=12)).strftime("%Y-%m-%dT%H:%M:%S")
            try:
                data = await _openf1(
                    "location",
                    {"session_key": status.session_key, "date>": since},
                )
            except Exception:
                data = []
            if isinstance(data, list) and data:
                loc = data
        if not loc:
            for window in windows:
                since = (now - timedelta(seconds=window)).strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    data = await _openf1(
                        "location",
                        {"session_key": status.session_key, "date>": since},
                    )
                except Exception:
                    data = []
                if isinstance(data, list) and data:
                    loc = data
                    break
        if isinstance(loc, list):
            for row in loc:
                num = row.get("driver_number")
                if num is None:
                    continue
                latest[int(num)] = row
            if _feed_session_key() == status.session_key:
                _STATE["locations"] = latest
    eliminated = _STATE.get("eliminated") or set()
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
        code = codes.get(num, f"D{num}")
        positions.append(
            LivePosition(
                driver_code=code,
                x=px,
                y=py,
                path_frac=frac,
                team_colour=colours.get(num),
                is_pitted=str(row.get("status") or "").lower() in {"pit", "inpit"},
                is_dnf=code in eliminated if isinstance(eliminated, set) else False,
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
    if replay_session_key is not None:
        pack = await _ensure_replay_pack(replay_session_key)
        clock = now_utc(as_of) if as_of is not None else pack.get("date_end")
        row = _weather_at(pack.get("weather") or [], clock if isinstance(clock, datetime) else None)
        return _weather_from_row(row, is_live=True)
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
    last = _weather_at(raw if isinstance(raw, list) else [], as_of)
    return _weather_from_row(last, is_live=True)


async def sse_generator(replay_session_key: int | None = None):
    while True:
        status = await live_status(replay_session_key=replay_session_key)
        timing = await live_timing(replay_session_key=replay_session_key)
        weather = await live_weather(replay_session_key=replay_session_key)
        payload = {
            "status": status.model_dump(mode="json"),
            "timing": timing.model_dump(mode="json"),
            "weather": weather.model_dump(mode="json"),
        }
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(5 if not status.is_live else 2)


async def _poll_location(session_key: int) -> None:
    now = datetime.now(timezone.utc)
    have = bool(_STATE.get("locations"))
    windows = (6,) if have else (20, 120, 600)
    loc: list[Any] = []
    for window in windows:
        since = (now - timedelta(seconds=window)).strftime("%Y-%m-%dT%H:%M:%S")
        data = await _openf1("location", {"session_key": session_key, "date>": since})
        if isinstance(data, list) and data:
            loc = data
            break
    latest: dict[int, dict[str, Any]] = dict(_STATE.get("locations") or {})
    for row in loc:
        num = row.get("driver_number")
        if num is None:
            continue
        latest[int(num)] = row
    if latest:
        _STATE["locations"] = latest
        _STATE["last_success"] = now_utc()


async def _poll_laps(session_key: int) -> None:
    laps = await _openf1("laps", {"session_key": session_key})
    if isinstance(laps, list):
        _STATE["laps"] = laps


async def _poll_position(session_key: int) -> None:
    since = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S")
    raw = await _openf1("position", {"session_key": session_key, "date>": since})
    latest: dict[int, int] = dict(_STATE.get("latest_pos") or {})
    if isinstance(raw, list):
        for row in raw:
            num = row.get("driver_number")
            pos = row.get("position")
            if num is None or pos is None:
                continue
            latest[int(num)] = int(pos)
        _STATE["latest_pos"] = latest


async def poll_openf1_forever() -> None:
    """Background refresh that stays under OpenF1's 60 req/min paid cap."""
    slot = 0
    print("[ARIS] OpenF1 live poller started", flush=True)
    while True:
        try:
            sess = await peek_live_session()
            key = sess.get("session_key") if isinstance(sess, dict) else None
            if key is not None:
                key = int(key)
                if slot == 0:
                    await _driver_code_map(key)
                    await _poll_laps(key)
                    await _poll_location(key)
                    wx = await _openf1("weather", {"session_key": key})
                    if isinstance(wx, list):
                        cache.set(f"openf1:weather:{key}", wx)
                elif slot % 2 == 0:
                    await _poll_location(key)
                elif slot % 6 == 1:
                    await _poll_laps(key)
                elif slot % 6 == 3:
                    await _poll_position(key)
                elif slot % 16 == 5:
                    wx = await _openf1("weather", {"session_key": key})
                    if isinstance(wx, list):
                        cache.set(f"openf1:weather:{key}", wx)
                elif slot % 12 == 7:
                    rc = await _openf1("race_control", {"session_key": key})
                    if isinstance(rc, list):
                        _STATE["race_control"] = rc
                        cache.set(f"openf1:rc-flag:{key}", rc)
                elif slot % 14 == 9:
                    st = await _openf1("stints", {"session_key": key})
                    if isinstance(st, list):
                        _STATE["stints"] = st
        except asyncio.CancelledError:
            raise
        except Exception as extra:
            _STATE["error"] = str(extra)
            print(f"[ARIS] OpenF1 poll: {extra}", flush=True)
        slot += 1
        await asyncio.sleep(1.2)
